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

    // Financial summary
    var hasData = false
    var netWorth: Double = 0.0
    var safeToSpend: Double = 0.0
    var statementInfo: StatementInfo?
    var spendingBreakdown: [SpendingCategory] = []

    // Top expenses
    var topExpenses: [TopExpense] = []
    var expenseSource: String = "none"

    // Smart nudges
    var nudges: [SmartNudge] = []

    // Category customization
    var customCategories: [String] = []
    var showCategoryEditor: Bool = false

    // MARK: - Dependencies

    private let apiService = APIService.shared

    // MARK: - Public Methods

    /// Fetches the financial summary for the authenticated user
    func fetchFinancialSummary() async {
        guard let userId = AuthManager.shared.authToken else {
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

    /// Fetches top spending categories
    func fetchTopExpenses() async {
        guard let userId = AuthManager.shared.authToken else { return }

        do {
            let response = try await apiService.getTopExpenses(userId: userId)
            topExpenses = response.topExpenses
            expenseSource = response.source
        } catch {
            print("Failed to fetch top expenses: \(error)")
        }
    }

    /// Fetches smart nudges
    func fetchNudges() async {
        guard let userId = AuthManager.shared.authToken else { return }

        do {
            let response = try await apiService.getNudges(userId: userId)
            nudges = response.nudges
        } catch {
            print("Failed to fetch nudges: \(error)")
        }
    }

    /// Loads category preferences
    func loadCategoryPreferences() async {
        guard let userId = AuthManager.shared.authToken else { return }

        do {
            let response = try await apiService.getCategoryPreferences(userId: userId)
            customCategories = response.categories.map { $0.categoryName }
        } catch {
            print("Failed to load category preferences: \(error)")
        }
    }

    /// Updates category preferences
    func updateCategoryPreferences(_ categories: [String]) async {
        guard let userId = AuthManager.shared.authToken else { return }

        do {
            try await apiService.updateCategoryPreferences(userId: userId, categories: categories)
            customCategories = categories
        } catch {
            print("Failed to update category preferences: \(error)")
        }
    }

    /// Refreshes all data concurrently
    func refresh() async {
        async let summary: () = fetchFinancialSummary()
        async let expenses: () = fetchTopExpenses()
        async let nudgesData: () = fetchNudges()
        async let prefs: () = loadCategoryPreferences()

        _ = await (summary, expenses, nudgesData, prefs)
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
        hasData = summary.hasData
        netWorth = summary.netWorth ?? 0.0
        safeToSpend = summary.safeToSpend ?? 0.0
        statementInfo = summary.statementInfo
        spendingBreakdown = summary.spendingBreakdown ?? []
    }

    private func clearData() {
        hasData = false
        netWorth = 0.0
        safeToSpend = 0.0
        statementInfo = nil
        spendingBreakdown = []
    }
}
