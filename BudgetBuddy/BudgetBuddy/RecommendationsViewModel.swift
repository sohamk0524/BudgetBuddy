//
//  RecommendationsViewModel.swift
//  BudgetBuddy
//
//  ViewModel for the Recommendations dashboard tab.
//

import SwiftUI
import Combine

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
    private var generalRecommendations: [RecommendationItem] = []

    private var cancellables = Set<AnyCancellable>()

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
        guard let category = activeCategory else { return recommendations }
        let keywords = Self.categoryKeywords[category] ?? [category]
        return recommendations.filter { item in
            let searchable = [item.title, item.description, item.spendingContext ?? ""]
                .joined(separator: " ").lowercased()
            return keywords.contains { searchable.contains($0) }
        }
    }

    var activeCategoryDisplayName: String {
        guard let category = activeCategory else { return "All" }
        return category.prefix(1).uppercased() + category.dropFirst()
    }

    var activeCategoryIcon: String {
        guard let category = activeCategory else { return "lightbulb" }
        return moneyMovesCards.first { $0.category == category }?.icon ?? "lightbulb"
    }

    private static let categoryKeywords: [String: [String]] = [
        "food": ["food", "restaurant", "dining", "eat", "meal", "lunch", "dinner", "breakfast", "fast food", "chipotle", "mcdonald"],
        "drink": ["drink", "coffee", "cafe", "tea", "starbucks", "boba", "bar", "smoothie"],
        "groceries": ["grocery", "groceries", "supermarket", "trader joe", "walmart", "costco", "aldi"],
        "transportation": ["transport", "gas", "uber", "lyft", "ride", "bus", "transit", "parking", "fuel"],
        "entertainment": ["entertainment", "movie", "streaming", "spotify", "netflix", "gaming", "concert", "event"],
        "other": ["subscription", "recurring", "amazon", "online"]
    ]

    // MARK: - Actions

    private var hasLoaded = false

    func loadRecommendations() async {
        guard !hasLoaded else { return }
        guard let userId = AuthManager.shared.authToken else { return }
        isLoading = true
        errorMessage = nil

        do {
            let response = try await APIService.shared.getRecommendations(userId: userId)
            apply(response)
            hasLoaded = true
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
            apply(response)
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
        if activeCategory == nil {
            generalRecommendations = recommendations
        }
        withAnimation(.spring(response: 0.3, dampingFraction: 0.8)) {
            activeCategory = category
        }
        Task { await generateRecommendations(action: category) }
    }

    func clearCategoryFilter() {
        withAnimation(.spring(response: 0.3, dampingFraction: 0.8)) {
            activeCategory = nil
            recommendations = generalRecommendations
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

    // MARK: - Private

    private func apply(_ response: RecommendationsResponse) {
        recommendations = response.recommendations
        safeToSpend = response.safeToSpend ?? safeToSpend
        status = response.status ?? status
        summary = response.summary ?? summary
    }
}
