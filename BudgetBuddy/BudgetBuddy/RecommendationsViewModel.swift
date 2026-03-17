//
//  RecommendationsViewModel.swift
//  BudgetBuddy
//
//  ViewModel for the Recommendations dashboard tab.
//

import SwiftUI
import Combine

enum RecommendationFilterMode: String, CaseIterable {
    case all = "All"
    case saved = "Saved"
    case used = "Used"
    case challenges = "Challenges"
}

@Observable
@MainActor
class RecommendationsViewModel {

    // MARK: - State

    var recommendations: [RecommendationItem] = []
    var safeToSpend: Double = 0
    var status: String = "unknown"
    var summary: String = ""
    var isLoading = false
    var isGenerating = false
    var errorMessage: String?

    // Money Moves
    var moneyMovesCards: [MoneyMovesCard] = []
    var activeCategory: String?

    // Search
    var searchQuery: String = ""
    var searchResults: [RecommendationItem] = []
    var isSearching = false
    var isSearchActive = false

    private var cancellables = Set<AnyCancellable>()

    // Save / Dislike / Used
    var filterMode: RecommendationFilterMode = .all
    var savedTipIds: Set<String> = []
    var savedTips: [RecommendationItem] = []
    var dislikedTipIds: Set<String> = []
    var usedTipIds: Set<String> = []
    var usedTips: [RecommendationItem] = []

    // Gamification
    var savingsStreak: Int = 0
    var longestStreak: Int = 0
    var totalSaved: Double = 0
    var challengesEnabled: Bool = true
    var weeklyChallenge: WeeklyChallenge?
    var challengeHistory: [ChallengeHistoryEntry] = []

    // Generic undo system
    enum UndoAction: String {
        case dislike = "Removed"
        case saved = "Saved"
        case used = "Marked as Used"
    }
    var pendingUndo: (action: UndoAction, item: RecommendationItem)?
    private var undoTimer: Task<Void, Never>?

    init() {
        NotificationCenter.default.publisher(for: .transactionAdded)
            .receive(on: RunLoop.main)
            .sink { [weak self] _ in
                guard let self else { return }
                Task { await self.refreshFinancialData() }
            }
            .store(in: &cancellables)
    }

    // MARK: - Computed

    var isHealthy: Bool {
        status == "on_track" || status == "unknown"
    }

    /// Daily safe-to-spend: distribute the remaining weekly budget across the remaining days (today through Sunday).
    var dailySafeToSpend: Double {
        let calendar = Calendar.current
        let weekday = calendar.component(.weekday, from: Date()) // 1 = Sunday, 7 = Saturday
        // Days remaining including today (Sunday = 1 day left, Monday = 7 days left)
        let daysRemaining = max(1, 8 - weekday)
        return (safeToSpend / Double(daysRemaining)).rounded(.down)
    }

    var statusDisplayText: String {
        switch status {
        case "on_track": return "On Track"
        case "caution": return "Caution"
        case "over_budget": return "Over Budget"
        default: return "—"
        }
    }

    var displayedRecommendations: [RecommendationItem] {
        let base: [RecommendationItem]
        switch filterMode {
        case .saved:
            base = savedTips

        case .used:
            base = usedTips

        case .challenges:
            base = []  // Challenges tab uses its own view

        case .all:
            base = recommendations.filter { !dislikedTipIds.contains($0.id) && !usedTipIds.contains($0.id) && !savedTipIds.contains($0.id) }
        }

        guard let category = activeCategory else { return base }
        let keywords = Self.categoryKeywords[category] ?? [category]
        return base.filter { item in
            if let tag = item.spendingCategory { return tag == category }
            let searchable = [item.title, item.description, item.spendingContext ?? ""]
                .joined(separator: " ").lowercased()
            return keywords.contains { searchable.contains($0) }
        }
    }

    var activeCategoryDisplayName: String {
        guard let category = activeCategory else { return "All" }
        return CategoryManager.shared.displayName(for: category)
    }

    var activeCategoryIcon: String {
        guard let category = activeCategory else { return "lightbulb" }
        return moneyMovesCards.first { $0.category == category }?.icon
            ?? CategoryManager.shared.icon(for: category)
    }

    /// Keywords for category filtering — pulls from the known category registry
    /// so both builtins and custom categories get rich keyword matching.
    private static var categoryKeywords: [String: [String]] {
        var keywords: [String: [String]] = [:]
        for cat in CategoryManager.shared.categories {
            keywords[cat.name] = CategoryManager.shared.keywords(for: cat.name)
        }
        return keywords
    }

    // MARK: - Actions

    private var hasLoaded = false

    func loadRecommendations() async {
        guard !hasLoaded else { return }
        guard let userId = AuthManager.shared.authToken else { return }
        isLoading = true
        errorMessage = nil

        do {
            async let recsResponse = APIService.shared.getRecommendations(userId: userId)
            async let prefsResponse = APIService.shared.getRecommendationPreferences(userId: userId)

            let recs = try await recsResponse
            apply(recs)

            let prefs = try await prefsResponse
            savedTips = prefs.savedTips
            savedTipIds = Set(prefs.savedTips.map { $0.id })
            dislikedTipIds = Set(prefs.dislikedTipIds)
            usedTips = prefs.seenTips ?? []
            usedTipIds = Set(prefs.seenTipIds ?? usedTips.map { $0.id })

            hasLoaded = true

            // Auto-generate if no cached recommendations exist
            if recommendations.isEmpty {
                isLoading = false
                await generateRecommendations()
                return
            }
        } catch {
            errorMessage = "Could not load recommendations."
        }

        isLoading = false
    }

    func generateRecommendations(action: String = "general") async {
        guard let userId = AuthManager.shared.authToken else { return }
        isGenerating = true
        errorMessage = nil

        do {
            let response = try await APIService.shared.generateRecommendations(userId: userId, action: action)
            if action == "general" {
                apply(response)
            } else {
                merge(response)
            }
        } catch {
            errorMessage = "Failed to generate recommendations."
        }

        isGenerating = false
    }

    func loadSpendingSummary() async {
        guard let userId = AuthManager.shared.authToken else { return }
        do {
            let response = try await APIService.shared.getSpendingSummary(userId: userId)
            moneyMovesCards = Array(response.categories.prefix(3))
        } catch {
            // Silently fail — Money Moves row just won't appear
        }
    }

    func selectCategory(_ category: String) {
        withAnimation(.spring(response: 0.3, dampingFraction: 0.8)) {
            activeCategory = category
        }

        // Auto-generate if no existing recs match this category
        if displayedRecommendations.isEmpty && filterMode == .all {
            Task { await generateRecommendations(action: category) }
        }
    }

    func clearCategoryFilter() {
        withAnimation(.spring(response: 0.3, dampingFraction: 0.8)) {
            activeCategory = nil
        }
    }

    func searchDeals() async {
        let query = searchQuery.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !query.isEmpty else { return }
        guard let userId = AuthManager.shared.authToken else { return }

        isSearching = true
        isSearchActive = true
        searchResults = []

        do {
            let response = try await APIService.shared.generateRecommendations(
                userId: userId,
                searchQuery: query
            )
            searchResults = response.recommendations
        } catch {
            errorMessage = "Search failed. Please try again."
        }

        isSearching = false
    }

    func clearSearch() {
        withAnimation(.spring(response: 0.3, dampingFraction: 0.8)) {
            searchQuery = ""
            searchResults = []
            isSearchActive = false
        }
    }

    func loadGamification() async {
        guard let userId = AuthManager.shared.authToken else { return }
        do {
            let data = try await APIService.shared.getGamification(userId: userId)
            savingsStreak = data.savingsStreak
            longestStreak = data.longestStreak
            totalSaved = data.totalSaved
            challengesEnabled = data.challengesEnabled ?? true
            weeklyChallenge = data.weeklyChallenge
            challengeHistory = data.challengeHistory ?? []
        } catch {
            // Silently fail — gamification is non-critical
        }
    }

    func acceptChallenge() async {
        guard let userId = AuthManager.shared.authToken else { return }
        do {
            let response = try await APIService.shared.respondToChallenge(userId: userId, action: "accept")
            weeklyChallenge = response.weeklyChallenge
        } catch {
            // Silently fail
        }
    }

    func declineChallenge() async {
        guard let userId = AuthManager.shared.authToken else { return }
        do {
            let response = try await APIService.shared.respondToChallenge(userId: userId, action: "decline")
            weeklyChallenge = response.weeklyChallenge
        } catch {
            // Silently fail
        }
    }

    /// Dismiss the weekly challenge — persists to backend and archives if accepted.
    func dismissChallenge() async {
        guard let userId = AuthManager.shared.authToken else { return }
        weeklyChallenge = nil
        do {
            _ = try await APIService.shared.respondToChallenge(userId: userId, action: "dismiss")
        } catch {
            // Silently fail
        }
    }

    /// Toggle challenge generation on/off.
    func toggleChallenges(enabled: Bool) async {
        guard let userId = AuthManager.shared.authToken else { return }
        challengesEnabled = enabled
        if !enabled { weeklyChallenge = nil }
        do {
            try await APIService.shared.toggleChallenges(userId: userId, enabled: enabled)
        } catch {
            // Revert on failure
            challengesEnabled = !enabled
        }
    }

    func refreshFinancialData() async {
        guard let userId = AuthManager.shared.authToken else { return }
        do {
            let summary = try await APIService.shared.getFinancialSummary(userId: userId)
            if let newSafe = summary.safeToSpend {
                safeToSpend = newSafe
            }
        } catch {
            // Silently fail — stale value is acceptable
        }
    }

    // MARK: - Save / Bookmark

    func toggleSave(_ item: RecommendationItem) {
        let wasSaved = savedTipIds.contains(item.id)

        // Commit any pending undo first
        commitPendingAction()

        if wasSaved {
            // Unsave — move back to all
            savedTipIds.remove(item.id)
            savedTips.removeAll { $0.id == item.id }
        } else {
            // Save — enforce mutual exclusivity
            removeFromAllStates(item)
            savedTipIds.insert(item.id)
            savedTips.append(item)

            // Show undo toast
            showUndo(.saved, item: item)
        }

        // Fire-and-forget API call
        guard let userId = AuthManager.shared.authToken else { return }
        Task {
            do {
                let _ = try await APIService.shared.saveRecommendation(userId: userId, recommendation: item)
            } catch {
                // Revert on failure
                if wasSaved {
                    savedTipIds.insert(item.id)
                    savedTips.append(item)
                } else {
                    savedTipIds.remove(item.id)
                    savedTips.removeAll { $0.id == item.id }
                }
            }
        }
    }

    // MARK: - Dislike

    func dislike(_ item: RecommendationItem) {
        commitPendingAction()

        // Enforce mutual exclusivity
        removeFromAllStates(item)
        dislikedTipIds.insert(item.id)

        showUndo(.dislike, item: item)

        // Fire API call
        guard let userId = AuthManager.shared.authToken else { return }
        Task {
            do {
                try await APIService.shared.dislikeRecommendation(userId: userId, tipId: item.id)
            } catch {
                // Silently fail — tip stays hidden locally
            }
        }
    }

    // MARK: - Mark Used

    func markUsed(_ item: RecommendationItem) {
        commitPendingAction()

        // Enforce mutual exclusivity
        removeFromAllStates(item)
        usedTipIds.insert(item.id)
        usedTips.append(item)

        showUndo(.used, item: item)

        // Fire API calls
        guard let userId = AuthManager.shared.authToken else { return }
        Task {
            do {
                try await APIService.shared.markRecommendationSeen(userId: userId, recommendation: item)
            } catch {
                // Silently fail — tip stays hidden locally
            }
            // Report savings if the tip has a potentialSavings value
            let savings = item.potentialSavings ?? 0
            if savings > 0 {
                do {
                    try await APIService.shared.reportUsedSavings(userId: userId, amount: savings)
                    totalSaved += savings
                } catch {
                    // Silently fail — savings counter is non-critical
                }
            }
        }
    }

    func restoreFromUsed(_ item: RecommendationItem) {
        usedTipIds.remove(item.id)
        usedTips.removeAll { $0.id == item.id }
    }

    // MARK: - Generic Undo

    func undoLastAction() {
        guard let undo = pendingUndo else { return }
        undoTimer?.cancel()
        undoTimer = nil

        switch undo.action {
        case .dislike:
            dislikedTipIds.remove(undo.item.id)
        case .saved:
            savedTipIds.remove(undo.item.id)
            savedTips.removeAll { $0.id == undo.item.id }
        case .used:
            usedTipIds.remove(undo.item.id)
            usedTips.removeAll { $0.id == undo.item.id }
        }

        pendingUndo = nil
    }

    func commitPendingAction() {
        guard pendingUndo != nil else { return }
        undoTimer?.cancel()
        undoTimer = nil
        pendingUndo = nil
    }

    // MARK: - Private

    private func removeFromAllStates(_ item: RecommendationItem) {
        savedTipIds.remove(item.id)
        savedTips.removeAll { $0.id == item.id }
        dislikedTipIds.remove(item.id)
        usedTipIds.remove(item.id)
        usedTips.removeAll { $0.id == item.id }
    }

    private func showUndo(_ action: UndoAction, item: RecommendationItem) {
        pendingUndo = (action: action, item: item)

        undoTimer?.cancel()
        undoTimer = Task {
            try? await Task.sleep(nanoseconds: 5_000_000_000)
            guard !Task.isCancelled else { return }
            commitPendingAction()
        }
    }

    private func apply(_ response: RecommendationsResponse) {
        recommendations = response.recommendations.filter { !dislikedTipIds.contains($0.id) && !usedTipIds.contains($0.id) }
        safeToSpend = response.safeToSpend ?? safeToSpend
        status = response.status ?? status
        summary = response.summary ?? summary
    }

    /// Merges category-specific results into the existing list without removing other tips.
    private func merge(_ response: RecommendationsResponse) {
        let existingIds = Set(recommendations.map { $0.id })
        let newRecs = response.recommendations.filter {
            !existingIds.contains($0.id) && !dislikedTipIds.contains($0.id) && !usedTipIds.contains($0.id)
        }
        recommendations.append(contentsOf: newRecs)
        safeToSpend = response.safeToSpend ?? safeToSpend
        status = response.status ?? status
        summary = response.summary ?? summary
    }
}
