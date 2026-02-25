//
//  RecommendationsViewModel.swift
//  BudgetBuddy
//
//  ViewModel for the Recommendations dashboard tab.
//

import SwiftUI

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

    func loadRecommendations() async {
        guard let userId = AuthManager.shared.authToken else { return }
        isLoading = true
        errorMessage = nil

        do {
            let response = try await APIService.shared.getRecommendations(userId: userId)
            apply(response)
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

    // MARK: - Private

    private func apply(_ response: RecommendationsResponse) {
        recommendations = response.recommendations
        safeToSpend = response.safeToSpend ?? safeToSpend
        status = response.status ?? status
        summary = response.summary ?? summary
    }
}
