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
    case mixed = "Mixed"
}

@Observable
@MainActor
class ExpensesViewModel {

    // MARK: - State

    var isLoading = false
    var errorMessage: String?

    var transactions: [ExpenseTransaction] = []
    var summary = ExpensesSummary(totalEssential: 0, totalDiscretionary: 0, totalMixed: 0, totalUnclassified: 0)
    var total = 0
    var hasMore = false

    var selectedFilter: ExpenseFilter = .all
    var startDate: String?
    var endDate: String?

    var unclassifiedMerchants: [UnclassifiedMerchant] = []
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
        case .mixed: "mixed"
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
        case .mixed: "mixed"
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

    func fetchUnclassifiedMerchants() async {
        guard let userId = AuthManager.shared.authToken else { return }

        do {
            let response = try await apiService.getUnclassifiedMerchants(userId: userId)
            unclassifiedMerchants = response.merchants
        } catch {
            print("Failed to fetch unclassified merchants: \(error)")
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
            // Remove from unclassified list
            unclassifiedMerchants.removeAll { $0.merchantName == merchantName }
            // Refresh expenses to show updated classifications
            await fetchExpenses()
        } catch {
            print("Failed to classify merchant: \(error)")
        }
    }

    func classifyTransaction(transactionId: Int, subCategory: String, essentialRatio: Double? = nil) async {
        do {
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
            showClassificationSheet = false
            // Refresh summary
            await fetchExpenses()
        } catch {
            print("Failed to classify transaction: \(error)")
        }
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
        async let merchants: () = fetchUnclassifiedMerchants()
        _ = await (expenses, merchants)
    }
}
