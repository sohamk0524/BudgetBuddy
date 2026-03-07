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

    var statusDisplayText: String {
        switch status {
        case "on_track": return "On Track"
        case "caution": return "Caution"
        case "over_budget": return "Over Budget"
        default: return "—"
        }
    }

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
