//
//  RecommendationsViewModel.swift
//  BudgetBuddy
//
//  ViewModel for the Recommendations dashboard tab.
//

import SwiftUI
import Combine

enum RecommendationFilterMode {
    case all
    case saved
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
    private var cancellables = Set<AnyCancellable>()

    // Save / Dislike
    var filterMode: RecommendationFilterMode = .all
    var savedTipIds: Set<String> = []
    var savedTips: [RecommendationItem] = []
    var dislikedTipIds: Set<String> = []
    var undoableDismissal: (item: RecommendationItem, index: Int)?
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
        switch filterMode {
        case .saved:
            if let category = activeCategory {
                let keywords = Self.categoryKeywords[category] ?? [category]
                return savedTips.filter { item in
                    if let tag = item.spendingCategory { return tag == category }
                    let searchable = [item.title, item.description, item.spendingContext ?? ""]
                        .joined(separator: " ").lowercased()
                    return keywords.contains { searchable.contains($0) }
                }
            }
            return savedTips

        case .all:
            let filtered = recommendations.filter { !dislikedTipIds.contains($0.id) }
            guard let category = activeCategory else { return filtered }
            let keywords = Self.categoryKeywords[category] ?? [category]
            return filtered.filter { item in
                if let tag = item.spendingCategory { return tag == category }
                let searchable = [item.title, item.description, item.spendingContext ?? ""]
                    .joined(separator: " ").lowercased()
                return keywords.contains { searchable.contains($0) }
            }
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

        // Optimistic update
        if wasSaved {
            savedTipIds.remove(item.id)
            savedTips.removeAll { $0.id == item.id }
        } else {
            savedTipIds.insert(item.id)
            savedTips.append(item)
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
        // If there's already a pending undo, commit it first
        if undoableDismissal != nil {
            commitDislike()
        }

        // Find the item's index in the current recommendations for undo reinsertion
        let index = recommendations.firstIndex(where: { $0.id == item.id }) ?? recommendations.count

        // Optimistic update
        dislikedTipIds.insert(item.id)
        savedTipIds.remove(item.id)
        savedTips.removeAll { $0.id == item.id }

        undoableDismissal = (item: item, index: index)

        // Start undo timer (5 seconds)
        undoTimer?.cancel()
        undoTimer = Task {
            try? await Task.sleep(nanoseconds: 5_000_000_000)
            guard !Task.isCancelled else { return }
            commitDislike()
        }
    }

    func undoDislike() {
        guard let dismissal = undoableDismissal else { return }
        undoTimer?.cancel()
        undoTimer = nil

        // Revert
        dislikedTipIds.remove(dismissal.item.id)
        undoableDismissal = nil
    }

    func commitDislike() {
        guard let dismissal = undoableDismissal else { return }
        undoTimer?.cancel()
        undoTimer = nil
        undoableDismissal = nil

        // Fire API call
        guard let userId = AuthManager.shared.authToken else { return }
        Task {
            do {
                try await APIService.shared.dislikeRecommendation(userId: userId, tipId: dismissal.item.id)
            } catch {
                // Silently fail — tip stays hidden locally
            }
        }
    }

    // MARK: - Private

    private func apply(_ response: RecommendationsResponse) {
        recommendations = response.recommendations.filter { !dislikedTipIds.contains($0.id) }
        safeToSpend = response.safeToSpend ?? safeToSpend
        status = response.status ?? status
        summary = response.summary ?? summary
    }

    /// Merges category-specific results into the existing list without removing other tips.
    private func merge(_ response: RecommendationsResponse) {
        let existingIds = Set(recommendations.map { $0.id })
        let newRecs = response.recommendations.filter {
            !existingIds.contains($0.id) && !dislikedTipIds.contains($0.id)
        }
        recommendations.append(contentsOf: newRecs)
        safeToSpend = response.safeToSpend ?? safeToSpend
        status = response.status ?? status
        summary = response.summary ?? summary
    }
}
