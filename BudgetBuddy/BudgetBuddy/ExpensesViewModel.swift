//
//  ExpensesViewModel.swift
//  BudgetBuddy
//
//  ViewModel for the Expenses tab - manages expense categorization state
//

import Foundation

enum ExpenseFilter: String, CaseIterable {
    case all = "All"
    case food = "Food"
    case drink = "Drink"
    case groceries = "Groceries"
    case transportation = "Transportation"
    case entertainment = "Entertainment"
    case other = "Other"
    case unclassified = "Unclassified"
}

@Observable
@MainActor
class ExpensesViewModel {

    // MARK: - State

    var isLoading = false
    var errorMessage: String?

    /// Full unfiltered transaction list — source of truth for all derived state.
    private var allTransactions: [ExpenseTransaction] = []

    /// Filtered view used by the UI. Computed locally — no API call on filter change.
    var transactions: [ExpenseTransaction] {
        switch selectedFilter {
        case .all:             return allTransactions
        case .food:            return allTransactions.filter { $0.subCategory.lowercased() == "food" }
        case .drink:           return allTransactions.filter { $0.subCategory.lowercased() == "drink" }
        case .groceries:       return allTransactions.filter { $0.subCategory.lowercased() == "groceries" }
        case .transportation:  return allTransactions.filter { $0.subCategory.lowercased() == "transportation" }
        case .entertainment:   return allTransactions.filter { $0.subCategory.lowercased() == "entertainment" }
        case .other:           return allTransactions.filter { $0.subCategory.lowercased() == "other" }
        case .unclassified:    return allTransactions.filter { isUnclassified($0) }
        }
    }

    /// Summary computed locally from the full list.
    var summary: ExpensesSummary {
        let knownCategories = ["food", "drink", "groceries", "transportation", "entertainment", "other"]
        var totals = [String: Double]()
        for cat in knownCategories {
            totals[cat] = allTransactions.filter { $0.subCategory.lowercased() == cat }.reduce(0) { $0 + $1.amount }
        }
        let unclassified = allTransactions.filter { isUnclassified($0) }.reduce(0.0) { $0 + $1.amount }
        return ExpensesSummary(
            totalFood: totals["food"] ?? 0,
            totalDrink: totals["drink"] ?? 0,
            totalGroceries: totals["groceries"] ?? 0,
            totalTransportation: totals["transportation"] ?? 0,
            totalEntertainment: totals["entertainment"] ?? 0,
            totalOther: totals["other"] ?? 0,
            totalUnclassified: unclassified
        )
    }

    /// Number of weeks of history currently loaded (default = 2).
    private(set) var weeksBack: Int = 2
    var isLoadingMore = false

    var selectedFilter: ExpenseFilter = .all

    var selectedTransaction: ExpenseTransaction?
    var showClassificationSheet = false

    // MARK: - Dependencies

    private let apiService = APIService.shared

    // MARK: - Week-based date helpers

    private var fetchStartDate: String {
        let start = Calendar.current.date(byAdding: .day, value: -(weeksBack * 7), to: Date()) ?? Date()
        return Self.isoDateFormatter.string(from: start)
    }

    private var fetchEndDate: String {
        Self.isoDateFormatter.string(from: Date())
    }

    private static let isoDateFormatter: DateFormatter = {
        let df = DateFormatter()
        df.dateFormat = "yyyy-MM-dd"
        return df
    }()

    private static func parseDate(_ s: String) -> Date? {
        isoDateFormatter.date(from: s)
    }

    private static func weekStart(for date: Date, cal: Calendar) -> Date {
        let weekday = cal.component(.weekday, from: date)
        let daysSinceMonday = (weekday - cal.firstWeekday + 7) % 7
        return cal.startOfDay(for: cal.date(byAdding: .day, value: -daysSinceMonday, to: date)!)
    }

    /// Human-readable date range for the current fetch window.
    var rangeLabel: String {
        guard let start = Self.isoDateFormatter.date(from: fetchStartDate) else { return "" }
        let df = DateFormatter()
        df.dateFormat = "MMM d"
        return "\(df.string(from: start)) – Today"
    }

    /// Filtered transactions grouped by calendar week (Mon–Sun), most-recent week first.
    var transactionsByWeek: [(label: String, items: [ExpenseTransaction])] {
        var cal = Calendar(identifier: .gregorian)
        cal.firstWeekday = 2   // Monday
        let today = Date()
        let thisWeekStart = Self.weekStart(for: today, cal: cal)
        let lastWeekStart = cal.date(byAdding: .day, value: -7, to: thisWeekStart)!

        var groups: [Date: [ExpenseTransaction]] = [:]
        for txn in transactions {
            guard let dateStr = txn.date, let date = Self.parseDate(dateStr) else { continue }
            let ws = Self.weekStart(for: date, cal: cal)
            groups[ws, default: []].append(txn)
        }

        let labelFmt = DateFormatter()
        labelFmt.dateFormat = "MMM d"

        return groups.keys.sorted(by: >).map { weekStart in
            let label: String
            if weekStart == thisWeekStart {
                label = "This Week"
            } else if weekStart == lastWeekStart {
                label = "Last Week"
            } else {
                let weekEnd = cal.date(byAdding: .day, value: 6, to: weekStart) ?? weekStart
                label = "\(labelFmt.string(from: weekStart)) – \(labelFmt.string(from: weekEnd))"
            }
            let items = groups[weekStart]!.sorted {
                (Self.parseDate($0.date ?? "") ?? .distantPast) >
                (Self.parseDate($1.date ?? "") ?? .distantPast)
            }
            return (label: label, items: items)
        }
    }

    // MARK: - Public Methods

    func fetchExpenses() async {
        guard let userId = AuthManager.shared.authToken else { return }

        isLoading = true
        errorMessage = nil

        do {
            let response = try await apiService.getExpenses(
                userId: userId,
                startDate: fetchStartDate,
                endDate: fetchEndDate,
                subCategory: nil,
                limit: 500,
                offset: 0
            )
            allTransactions = response.transactions

            // Update daily reminder based on today's activity
            if hasLoggedTransactionToday() {
                NotificationManager.shared.cancelTodayNotification()
            } else {
                NotificationManager.shared.scheduleDailyReminder(hasLoggedToday: false)
            }
        } catch {
            print("Failed to fetch expenses: \(error)")
            errorMessage = "Unable to load expenses"
        }

        isLoading = false
    }

    /// Whether there is more history to load (under the 3-month cap).
    var canLoadMore: Bool { weeksBack < 13 }

    func loadPreviousWeek() async {
        guard let userId = AuthManager.shared.authToken else { return }
        guard canLoadMore else { return }

        isLoadingMore = true

        let maxWeeksBack = 13   // ~3 months absolute cap
        var totalNewFound = 0
        var lastFetchedCount = allTransactions.count

        while weeksBack < maxWeeksBack {
            weeksBack += 1

            do {
                let response = try await apiService.getExpenses(
                    userId: userId,
                    startDate: fetchStartDate,
                    endDate: fetchEndDate,
                    subCategory: nil,
                    limit: 500,
                    offset: 0
                )
                let newInThisWeek = response.transactions.count - lastFetchedCount
                lastFetchedCount = response.transactions.count
                allTransactions = response.transactions

                // End of available data — show whatever was found and stop
                if newInThisWeek <= 0 { break }

                totalNewFound += newInThisWeek

                // Accumulated enough new events
                if totalNewFound >= 5 { break }

            } catch {
                print("Failed to load previous week: \(error)")
                weeksBack -= 1
                break
            }
        }

        isLoadingMore = false
    }

    func classifyTransaction(transactionId: Int, subCategory: String) async {
        do {
            _ = try await classifyTransactionForSheet(transactionId: transactionId, subCategory: subCategory)
            showClassificationSheet = false

            // Classification means activity — cancel today's reminder
            NotificationManager.shared.cancelTodayNotification()
        } catch {
            print("Failed to classify transaction: \(error)")
        }
    }

    /// Classifies a transaction and returns the response. Does NOT dismiss the sheet — caller handles dismissal.
    func classifyTransactionForSheet(transactionId: Int, subCategory: String) async throws -> ClassifyTransactionResponse {
        let response = try await apiService.classifyTransaction(
            transactionId: transactionId,
            subCategory: subCategory
        )

        // Update local record immediately — no refetch needed for single classification
        applyClassificationLocally(
            transactionId: transactionId,
            subCategory: response.transaction.subCategory,
            essentialAmount: response.transaction.essentialAmount,
            discretionaryAmount: response.transaction.discretionaryAmount
        )

        // If the backend bulk-applied to other transactions, refresh in the background
        if (response.autoApplied ?? 0) > 0 {
            Task { await fetchExpenses() }
        }

        return response
    }

    func refresh() async {
        await fetchExpenses()
    }

    // MARK: - Private Helpers

    func hasLoggedTransactionToday() -> Bool {
        let calendar = Calendar.current
        return allTransactions.contains { txn in
            guard let dateStr = txn.date, let date = Self.parseDate(dateStr) else { return false }
            return calendar.isDateInToday(date)
        }
    }

    /// Returns true if a transaction has not been categorized yet.
    private func isUnclassified(_ txn: ExpenseTransaction) -> Bool {
        let known = ["food", "drink", "groceries", "transportation", "entertainment", "other"]
        return !known.contains(txn.subCategory.lowercased())
    }

    private func applyClassificationLocally(
        transactionId: Int,
        subCategory: String,
        essentialAmount: Double?,
        discretionaryAmount: Double?
    ) {
        guard let idx = allTransactions.firstIndex(where: { $0.id == transactionId }) else { return }
        let old = allTransactions[idx]
        allTransactions[idx] = ExpenseTransaction(
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
            subCategory: subCategory,
            essentialAmount: essentialAmount,
            discretionaryAmount: discretionaryAmount,
            source: old.source,
            notes: old.notes,
            receiptItems: old.receiptItems
        )
    }
}
