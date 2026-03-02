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

    /// Full unfiltered transaction list — source of truth for all derived state.
    private var allTransactions: [ExpenseTransaction] = []

    /// Filtered view used by the UI. Computed locally — no API call on filter change.
    var transactions: [ExpenseTransaction] {
        switch selectedFilter {
        case .all:          return allTransactions
        case .essential:    return allTransactions.filter { ($0.essentialAmount ?? 0) > 0.01 }
        case .discretionary: return allTransactions.filter { ($0.discretionaryAmount ?? 0) > 0.01 }
        case .unclassified: return allTransactions.filter { $0.subCategory == "unclassified" }
        }
    }

    /// Summary computed locally from the full list — always reflects the whole picture.
    var summary: ExpensesSummary {
        let essential = allTransactions.reduce(0.0) { $0 + ($1.essentialAmount ?? 0) }
        let discretionary = allTransactions.reduce(0.0) { $0 + ($1.discretionaryAmount ?? 0) }
        let unclassified = allTransactions
            .filter { $0.subCategory == "unclassified" }
            .reduce(0.0) { $0 + $1.amount }
        return ExpensesSummary(
            totalEssential: essential,
            totalDiscretionary: discretionary,
            totalFunMoney: discretionary,
            totalMixed: 0,
            totalUnclassified: unclassified
        )
    }

    /// Number of weeks of history currently loaded (default = 2).
    private(set) var weeksBack: Int = 2
    var isLoadingMore = false

    var selectedFilter: ExpenseFilter = .all

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

            let autoApplied = response.autoApplied ?? 0
            totalUnclassifiedCount -= (1 + autoApplied)
            if totalUnclassifiedCount < 0 { totalUnclassifiedCount = 0 }

            // Update local record immediately
            applyClassificationLocally(
                transactionId: transactionId,
                subCategory: response.transaction.subCategory,
                essentialAmount: response.transaction.essentialAmount,
                discretionaryAmount: response.transaction.discretionaryAmount
            )
            // Classification means activity — cancel today's reminder
            NotificationManager.shared.cancelTodayNotification()

            // If bulk auto-apply happened, refresh to capture all changed records
            if autoApplied > 0 {
                await fetchExpenses()
            }

            // Load next batch of cards if needed
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

            // Classification means activity — cancel today's reminder
            NotificationManager.shared.cancelTodayNotification()
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

    // MARK: - Private Helpers

    func hasLoggedTransactionToday() -> Bool {
        let calendar = Calendar.current
        return allTransactions.contains { txn in
            guard let dateStr = txn.date, let date = Self.parseDate(dateStr) else { return false }
            return calendar.isDateInToday(date)
        }
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
