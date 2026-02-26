//
//  ExpensesViewModel.swift
//  BudgetBuddy
//
//  ViewModel for the Expenses tab - manages expense classification state
//

import Foundation

enum ExpenseFilter: String, CaseIterable {
    case all = "All"
    case essential = "Essential"
    case discretionary = "Fun Money"
    case unclassified = "Unclassified"
}

@Observable
@MainActor
class ExpensesViewModel {

    // MARK: - State

    var isLoading = false
    var errorMessage: String?

    var transactions: [ExpenseTransaction] = []
    var summary = ExpensesSummary(totalEssential: 0, totalDiscretionary: 0, totalFunMoney: 0, totalMixed: 0, totalUnclassified: 0)
    var total = 0
    var hasMore = false

    var selectedFilter: ExpenseFilter = .all
    var startDate: String?
    var endDate: String?

    // Swipe classification state
    var unclassifiedTransactions: [UnclassifiedTransactionItem] = []
    var totalUnclassifiedCount: Int = 0
    var currentClassifyIndex: Int = 0
    var showSplitSheet = false
    var splitTransaction: UnclassifiedTransactionItem?

    var selectedTransaction: ExpenseTransaction?
    var showClassificationSheet = false
    var isAutoClassifying = false

    // MARK: - Dependencies

    private let apiService = APIService.shared
    private var currentOffset = 0
    private let pageSize = 50

    // MARK: - Public Methods

    func fetchExpenses() async {
        guard let userId = AuthManager.shared.authToken else { return }

        isLoading = true
        errorMessage = nil
        currentOffset = 0

        let subCategory: String? = switch selectedFilter {
        case .all: nil
        case .essential: "essential"
        case .discretionary: "discretionary"
        case .unclassified: "unclassified"
        }

        do {
            let response = try await apiService.getExpenses(
                userId: userId,
                startDate: startDate,
                endDate: endDate,
                subCategory: subCategory,
                limit: pageSize,
                offset: 0
            )
            transactions = response.transactions
            summary = response.summary
            total = response.total
            hasMore = response.hasMore
            currentOffset = pageSize
        } catch {
            print("Failed to fetch expenses: \(error)")
            errorMessage = "Unable to load expenses"
        }

        isLoading = false
    }

    func loadMore() async {
        guard hasMore, let userId = AuthManager.shared.authToken else { return }

        let subCategory: String? = switch selectedFilter {
        case .all: nil
        case .essential: "essential"
        case .discretionary: "discretionary"
        case .unclassified: "unclassified"
        }

        do {
            let response = try await apiService.getExpenses(
                userId: userId,
                startDate: startDate,
                endDate: endDate,
                subCategory: subCategory,
                limit: pageSize,
                offset: currentOffset
            )
            transactions.append(contentsOf: response.transactions)
            hasMore = response.hasMore
            currentOffset += pageSize
        } catch {
            print("Failed to load more expenses: \(error)")
        }
    }

    func fetchUnclassifiedTransactions() async {
        guard let userId = AuthManager.shared.authToken else { return }

        do {
            let response = try await apiService.getUnclassifiedTransactions(userId: userId, limit: 10)
            unclassifiedTransactions = response.transactions
            totalUnclassifiedCount = response.totalUnclassified
            currentClassifyIndex = 0
        } catch {
            print("Failed to fetch unclassified transactions: \(error)")
        }
    }

    func classifyViaSwipe(transactionId: Int, classification: String, essentialRatio: Double? = nil) async {
        do {
            let response = try await apiService.classifyTransaction(
                transactionId: transactionId,
                subCategory: classification,
                essentialRatio: essentialRatio
            )

            // Advance to next card
            currentClassifyIndex += 1

            // If auto-applied, reduce the unclassified count
            let autoApplied = response.autoApplied ?? 0
            totalUnclassifiedCount -= (1 + autoApplied)
            if totalUnclassifiedCount < 0 { totalUnclassifiedCount = 0 }

            // Refresh summary to reflect the new classification
            await fetchExpenses()

            // If we've gone through all loaded cards, fetch more
            if currentClassifyIndex >= unclassifiedTransactions.count {
                await fetchUnclassifiedTransactions()
            }
        } catch {
            print("Failed to classify via swipe: \(error)")
        }
    }

    func classifyMerchant(merchantName: String, classification: String, essentialRatio: Double? = nil) async {
        guard let userId = AuthManager.shared.authToken else { return }

        do {
            _ = try await apiService.classifyMerchant(
                userId: userId,
                merchantName: merchantName,
                classification: classification,
                essentialRatio: essentialRatio
            )
            await fetchExpenses()
        } catch {
            print("Failed to classify merchant: \(error)")
        }
    }

    func classifyTransaction(transactionId: Int, subCategory: String, essentialRatio: Double? = nil) async {
        do {
            _ = try await classifyTransactionForSheet(transactionId: transactionId, subCategory: subCategory, essentialRatio: essentialRatio)
            showClassificationSheet = false
        } catch {
            print("Failed to classify transaction: \(error)")
        }
    }

    /// Classifies a transaction and returns the response. Does NOT dismiss the sheet — caller handles dismissal.
    func classifyTransactionForSheet(transactionId: Int, subCategory: String, essentialRatio: Double? = nil) async throws -> ClassifyTransactionResponse {
        let response = try await apiService.classifyTransaction(
            transactionId: transactionId,
            subCategory: subCategory,
            essentialRatio: essentialRatio
        )
        // Update local state
        if let idx = transactions.firstIndex(where: { $0.id == transactionId }) {
            let old = transactions[idx]
            transactions[idx] = ExpenseTransaction(
                id: old.id,
                transactionId: old.transactionId,
                accountId: old.accountId,
                amount: old.amount,
                date: old.date,
                authorizedDate: old.authorizedDate,
                name: old.name,
                merchantName: old.merchantName,
                categoryPrimary: old.categoryPrimary,
                categoryDetailed: old.categoryDetailed,
                pending: old.pending,
                paymentChannel: old.paymentChannel,
                subCategory: response.transaction.subCategory,
                essentialAmount: response.transaction.essentialAmount,
                discretionaryAmount: response.transaction.discretionaryAmount
            )
        }
        await fetchExpenses()
        return response
    }

    func autoClassifyWithAI() async {
        guard let userId = AuthManager.shared.authToken else { return }

        isAutoClassifying = true
        do {
            _ = try await apiService.autoClassifyMerchants(userId: userId)
            await refresh()
        } catch {
            print("Failed to auto-classify: \(error)")
        }
        isAutoClassifying = false
    }

    func refresh() async {
        async let expenses: () = fetchExpenses()
        async let unclassified: () = fetchUnclassifiedTransactions()
        _ = await (expenses, unclassified)
    }
}
