//
//  WalletViewModel.swift
//  BudgetBuddy
//
//  ViewModel for the Wallet tab - manages financial summary state
//

import Foundation

@Observable
@MainActor
class WalletViewModel {

    // MARK: - Published State

    var isLoading = false
    var errorMessage: String?

    // Financial summary from saved statement
    var hasStatement = false
    var netWorth: Double = 0.0
    var safeToSpend: Double = 0.0
    var statementInfo: StatementInfo?
    var spendingBreakdown: [SpendingCategory] = []

    // MARK: - Dependencies

    private let apiService = APIService.shared

    // MARK: - Public Methods

    /// Fetches the financial summary for the authenticated user
    func fetchFinancialSummary() async {
        guard let userId = AuthManager.shared.authToken else {
            // Not authenticated - clear data
            clearData()
            return
        }

        isLoading = true
        errorMessage = nil

        do {
            let summary = try await apiService.getFinancialSummary(userId: userId)
            updateFromSummary(summary)
        } catch {
            print("Failed to fetch financial summary: \(error)")
            errorMessage = "Unable to load financial data"
            clearData()
        }

        isLoading = false
    }

    /// Refreshes the financial summary (called after statement upload)
    func refresh() async {
        await fetchFinancialSummary()
    }

    /// Deletes the user's saved statement
    func deleteStatement() async {
        guard let userId = AuthManager.shared.authToken else { return }

        isLoading = true
        errorMessage = nil

        do {
            try await apiService.deleteStatement(userId: userId)
            clearData()
        } catch {
            print("Failed to delete statement: \(error)")
            errorMessage = "Unable to delete statement"
        }

        isLoading = false
    }

    // MARK: - Private Methods

    private func updateFromSummary(_ summary: FinancialSummary) {
        hasStatement = summary.hasStatement
        netWorth = summary.netWorth ?? 0.0
        safeToSpend = summary.safeToSpend ?? 0.0
        statementInfo = summary.statementInfo
        spendingBreakdown = summary.spendingBreakdown ?? []
    }

    private func clearData() {
        hasStatement = false
        netWorth = 0.0
        safeToSpend = 0.0
        statementInfo = nil
        spendingBreakdown = []
    }
}
