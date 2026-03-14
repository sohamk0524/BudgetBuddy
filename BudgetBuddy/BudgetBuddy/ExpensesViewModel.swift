//
//  ExpensesViewModel.swift
//  BudgetBuddy
//
//  ViewModel for the Expenses tab - manages expense categorization state
//

import Foundation

extension Notification.Name {
    static let expensesDidChange = Notification.Name("expensesDidChange")
}

struct ExpenseFilter: Hashable {
    let name: String       // lowercase key or special: "all", "food", "unclassified"
    let displayName: String

    static let all = ExpenseFilter(name: "all", displayName: "All")
    static let unclassified = ExpenseFilter(name: "unclassified", displayName: "Unclassified")

    /// Generates the full filter list from CategoryManager.
    @MainActor static var allFilters: [ExpenseFilter] {
        var filters = [ExpenseFilter.all]
        filters += CategoryManager.shared.categories.map {
            ExpenseFilter(name: $0.name, displayName: $0.displayName)
        }
        filters.append(.unclassified)
        return filters
    }
}

@Observable
@MainActor
class ExpensesViewModel {

    // MARK: - UserDefaults Cache Keys

    private enum CacheKey {
        static let transactions = "expenses_transactions"
        static let weeksBack = "expenses_weeksBack"
    }

    // MARK: - State

    var isLoading = false
    var errorMessage: String?

    /// Full unfiltered transaction list — source of truth for all derived state.
    private var allTransactions: [ExpenseTransaction] = []

    /// Filtered view used by the UI. Computed locally — no API call on filter change.
    var transactions: [ExpenseTransaction] {
        if selectedFilter == .all {
            return allTransactions
        } else if selectedFilter == .unclassified {
            return allTransactions.filter { isUnclassified($0) }
        } else if selectedFilter.name == "other" {
            // "Other" includes actual "other" + orphaned categories from deleted custom categories
            return allTransactions.filter { $0.subCategory.lowercased() == "other" || isOrphaned($0) }
        } else {
            return allTransactions.filter { $0.subCategory.lowercased() == selectedFilter.name }
        }
    }

    /// Summary computed locally from the full list — supports custom categories.
    var summary: ExpensesSummary {
        var totals = [String: Double]()
        for cat in CategoryManager.shared.categories {
            if cat.name == "other" {
                // "Other" total includes orphaned categories
                totals[cat.name] = allTransactions
                    .filter { $0.subCategory.lowercased() == "other" || isOrphaned($0) }
                    .reduce(0) { $0 + $1.amount }
            } else {
                totals[cat.name] = allTransactions
                    .filter { $0.subCategory.lowercased() == cat.name }
                    .reduce(0) { $0 + $1.amount }
            }
        }
        let unclassified = allTransactions.filter { isUnclassified($0) }.reduce(0.0) { $0 + $1.amount }
        return ExpensesSummary(
            categoryTotals: totals,
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
    private let defaults = UserDefaults.standard

    // MARK: - Init

    init() {
        loadFromCache()
    }

    // MARK: - Clear (called on sign-out / account switch)

    func clearData() {
        allTransactions = []
        weeksBack = 2
        selectedFilter = .all
        selectedTransaction = nil
        showClassificationSheet = false
        isLoading = false
        errorMessage = nil
    }

    // MARK: - Cache

    private func loadFromCache() {
        if let data = defaults.data(forKey: CacheKey.transactions),
           let decoded = try? JSONDecoder().decode([ExpenseTransaction].self, from: data) {
            allTransactions = decoded
        }
        let cached = defaults.integer(forKey: CacheKey.weeksBack)
        if cached > 0 { weeksBack = cached }
    }

    private func saveToCache() {
        if let encoded = try? JSONEncoder().encode(allTransactions) {
            defaults.set(encoded, forKey: CacheKey.transactions)
        }
        defaults.set(weeksBack, forKey: CacheKey.weeksBack)
    }

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
            saveToCache()
            NotificationCenter.default.post(name: .expensesDidChange, object: nil)

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

        let startCount = allTransactions.count
        let maxNewItems = 10
        let maxWeeksToAdd = 4

        var weeksAdded = 0
        while weeksAdded < maxWeeksToAdd && canLoadMore {
            weeksBack += 1
            weeksAdded += 1

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
                saveToCache()
                NotificationCenter.default.post(name: .expensesDidChange, object: nil)

                if allTransactions.count - startCount >= maxNewItems { break }
            } catch {
                print("Failed to load more history: \(error)")
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
    func classifyTransactionForSheet(
        transactionId: Int,
        subCategory: String,
        amount: Double? = nil,
        merchantName: String? = nil,
        date: String? = nil
    ) async throws -> ClassifyTransactionResponse {
        let response = try await apiService.classifyTransaction(
            transactionId: transactionId,
            subCategory: subCategory,
            amount: amount,
            merchantName: merchantName,
            date: date
        )

        // Update local record immediately — no refetch needed for single classification
        applyClassificationLocally(
            transactionId: transactionId,
            subCategory: response.transaction.subCategory,
            essentialAmount: response.transaction.essentialAmount,
            discretionaryAmount: response.transaction.discretionaryAmount,
            amount: response.transaction.amount,
            merchantName: response.transaction.merchantName,
            date: response.transaction.date
        )

        NotificationCenter.default.post(name: .expensesDidChange, object: nil)

        // If the backend bulk-applied to other transactions, refresh in the background
        if (response.autoApplied ?? 0) > 0 {
            Task { await fetchExpenses() }
        }

        return response
    }

    func deleteTransaction(transactionId: Int) async throws {
        try await apiService.deleteTransaction(transactionId: transactionId)
        allTransactions.removeAll { $0.id == transactionId }
        saveToCache()
    }

    func addItemsToTransaction(transactionId: Int, items: [EditableReceiptItem], replace: Bool = false) async throws {
        let response = try await apiService.addReceiptItems(transactionId: transactionId, items: items, replace: replace)
        if let newSubCategory = response.subCategory {
            applyClassificationLocally(
                transactionId: transactionId,
                subCategory: newSubCategory,
                essentialAmount: nil,
                discretionaryAmount: nil
            )
        }
    }

    func refresh() async {
        // Wrap in a child Task so SwiftUI .refreshable cancellation
        // doesn't abort the in-flight network request.
        let task = Task { await fetchExpenses() }
        await task.value
    }

    // MARK: - Private Helpers

    func hasLoggedTransactionToday() -> Bool {
        let calendar = Calendar.current
        return allTransactions.contains { txn in
            guard let dateStr = txn.date, let date = Self.parseDate(dateStr) else { return false }
            return calendar.isDateInToday(date)
        }
    }

    /// Refresh immediately, then retry up to 3 more times (at 1s, 2s, 4s) until
    /// the transaction count increases — handles Datastore eventual-consistency lag.
    func refreshWithRetry() async {
        let countBefore = allTransactions.count
        await fetchExpenses()
        if allTransactions.count > countBefore { return }

        let delays: [UInt64] = [1_000_000_000, 2_000_000_000, 4_000_000_000]
        for delay in delays {
            try? await Task.sleep(nanoseconds: delay)
            await fetchExpenses()
            if allTransactions.count > countBefore { return }
        }
    }

    /// Optimistically insert a newly created transaction into the local list and cache.
    func insertTransactionLocally(_ transaction: ExpenseTransaction) {
        // Avoid duplicates (in case a background refresh already picked it up)
        guard !allTransactions.contains(where: { $0.id == transaction.id }) else { return }
        allTransactions.insert(transaction, at: 0)
        saveToCache()
    }

    /// Returns true if a transaction has never been categorized (empty subCategory).
    /// Orphaned categories (from deleted custom categories) are treated as "other", not unclassified.
    private func isUnclassified(_ txn: ExpenseTransaction) -> Bool {
        txn.subCategory.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
    }

    /// Returns true if this transaction's category is not in the current valid list
    /// (orphaned from a deleted custom category). These show under "Other".
    private func isOrphaned(_ txn: ExpenseTransaction) -> Bool {
        let cat = txn.subCategory.trimmingCharacters(in: .whitespacesAndNewlines)
        return !cat.isEmpty && !CategoryManager.shared.isValidCategory(cat)
    }

    private func applyClassificationLocally(
        transactionId: Int,
        subCategory: String,
        essentialAmount: Double?,
        discretionaryAmount: Double?,
        amount: Double? = nil,
        merchantName: String? = nil,
        date: String? = nil
    ) {
        guard let idx = allTransactions.firstIndex(where: { $0.id == transactionId }) else { return }
        let old = allTransactions[idx]
        allTransactions[idx] = ExpenseTransaction(
            id: old.id,
            transactionId: old.transactionId,
            accountId: old.accountId,
            amount: amount ?? old.amount,
            date: date ?? old.date,
            authorizedDate: old.authorizedDate,
            name: old.name,
            merchantName: merchantName ?? old.merchantName,
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
        saveToCache()
    }
}
