//
//  InsightsViewModel.swift
//  BudgetBuddy
//
//  ViewModel for the Insights tab — fetches transactions and computes chart data
//

import Foundation
import SwiftUI

@Observable
@MainActor
final class InsightsViewModel {

    // MARK: - Enums

    enum DateRange: String, CaseIterable, Identifiable {
        case week = "7 Days"

        var id: String { rawValue }

        var days: Int {
            switch self {
            case .week: return 7
            }
        }

        var label: String {
            switch self {
            case .week: return "Last 7 Days"
            }
        }
    }

    enum BarGrouping: String, CaseIterable, Identifiable {
        case daily = "Daily"
        case weekly = "Weekly"
        var id: String { rawValue }
    }

    // MARK: - Chart Data Types

    struct CategorySlice: Identifiable {
        let id: String
        let category: String
        let amount: Double
        let color: Color
        let icon: String
    }

    struct BarEntry: Identifiable {
        let id: String
        let date: Date
        let label: String
        let amount: Double
    }

    // MARK: - Cache Keys

    private static func cacheKey(for range: DateRange) -> String {
        "insights_transactions_\(range.rawValue)"
    }

    // MARK: - State

    var isLoading = false
    var errorMessage: String?
    private var allTransactions: [ExpenseTransaction] = []

    init() {
        loadFromCache(for: .week)   // pre-populate default range instantly
    }

    var selectedDateRange: DateRange = .week
    var selectedPieCategory: String? = nil
    var barGrouping: BarGrouping = .daily
    var selectedBarDate: Date? = nil

    // MARK: - Pie Chart Computed Data

    var pieData: [CategorySlice] {
        var totals: [String: Double] = [:]
        for tx in allTransactions {
            let cat = tx.subCategory.lowercased()
            guard !cat.isEmpty else { continue }
            totals[cat, default: 0] += abs(tx.amount)
        }
        return totals
            .filter { $0.value > 0 }
            .map { CategorySlice(id: $0.key, category: $0.key, amount: $0.value, color: categoryColor(for: $0.key), icon: categoryIcon(for: $0.key)) }
            .sorted { $0.amount > $1.amount }
    }

    var totalSpending: Double {
        pieData.reduce(0) { $0 + $1.amount }
    }

    var selectedCategoryTransactions: [ExpenseTransaction] {
        guard let cat = selectedPieCategory else { return [] }
        return allTransactions
            .filter { $0.subCategory.lowercased() == cat.lowercased() }
            .sorted { ($0.date ?? "") > ($1.date ?? "") }
            .prefix(10)
            .map { $0 }
    }

    // MARK: - Bar Chart Computed Data

    var barData: [BarEntry] {
        barGrouping == .daily ? dailyData : weeklyData
    }

    var barAverage: Double {
        let data = barData.filter { $0.amount > 0 }
        guard !data.isEmpty else { return 0 }
        return data.reduce(0) { $0 + $1.amount } / Double(data.count)
    }

    /// Amount for the currently selected (tapped) bar
    var selectedBarAmount: (label: String, amount: Double)? {
        guard let date = selectedBarDate,
              let entry = barData.first(where: { Calendar.current.isDate($0.date, inSameDayAs: date) }) else {
            return nil
        }
        return (entry.label, entry.amount)
    }

    private var dailyData: [BarEntry] {
        let cal = Calendar.current
        let fmt = Self.isoFmt

        var buckets: [String: Double] = [:]
        for tx in allTransactions {
            let cat = tx.subCategory.lowercased()
            guard !cat.isEmpty else { continue }
            guard let dateStr = tx.date, let d = fmt.date(from: dateStr) else { continue }
            let key = fmt.string(from: d)
            buckets[key, default: 0] += abs(tx.amount)
        }

        let start = cal.date(byAdding: .day, value: -selectedDateRange.days, to: Date())!
        let end = Date()
        var results: [BarEntry] = []
        var cursor = cal.startOfDay(for: start)

        let dayFmt = DateFormatter()
        dayFmt.dateFormat = selectedDateRange == .week ? "EEE" : "M/d"

        while cursor <= end {
            let key = fmt.string(from: cursor)
            results.append(BarEntry(id: key, date: cursor, label: dayFmt.string(from: cursor), amount: buckets[key] ?? 0))
            cursor = cal.date(byAdding: .day, value: 1, to: cursor)!
        }
        return results
    }

    private var weeklyData: [BarEntry] {
        let cal = Calendar.current
        let fmt = Self.isoFmt

        var weekBuckets: [Date: Double] = [:]
        for tx in allTransactions {
            let cat = tx.subCategory.lowercased()
            guard !cat.isEmpty else { continue }
            guard let dateStr = tx.date, let d = fmt.date(from: dateStr) else { continue }
            let comps = cal.dateComponents([.yearForWeekOfYear, .weekOfYear], from: d)
            let weekStart = cal.date(from: comps) ?? d
            weekBuckets[weekStart, default: 0] += abs(tx.amount)
        }

        let weekFmt = DateFormatter()
        weekFmt.dateFormat = "MMM d"

        return weekBuckets
            .sorted { $0.key < $1.key }
            .map { BarEntry(id: weekFmt.string(from: $0.key), date: $0.key, label: weekFmt.string(from: $0.key), amount: $0.value) }
    }

    // MARK: - Clear (called on sign-out / account switch)

    func clearData() {
        allTransactions = []
        selectedDateRange = .week
        selectedPieCategory = nil
        barGrouping = .daily
        selectedBarDate = nil
        isLoading = false
        errorMessage = nil
    }

    // MARK: - Actions

    // MARK: - Cache helpers

    private func loadFromCache(for range: DateRange) {
        let key = Self.cacheKey(for: range)
        guard let data = UserDefaults.standard.data(forKey: key),
              let decoded = try? JSONDecoder().decode([ExpenseTransaction].self, from: data) else { return }
        allTransactions = decoded
    }

    private func saveToCache(for range: DateRange) {
        let key = Self.cacheKey(for: range)
        if let encoded = try? JSONEncoder().encode(allTransactions) {
            UserDefaults.standard.set(encoded, forKey: key)
        }
    }

    func selectDateRange(_ range: DateRange) {
        selectedDateRange = range
        selectedPieCategory = nil
        selectedBarDate = nil
        loadFromCache(for: range)   // swap in cached data instantly before network call
        Task { await fetchTransactions() }
    }

    func togglePieCategory(_ category: String) {
        if selectedPieCategory == category {
            selectedPieCategory = nil
        } else {
            selectedPieCategory = category
        }
    }

    func fetchTransactions() async {
        guard let userId = AuthManager.shared.authToken else {
            print("[Insights] ❌ No auth token, skipping fetch")
            return
        }
        isLoading = true
        errorMessage = nil

        let start = Self.isoFmt.string(from: Calendar.current.date(byAdding: .day, value: -selectedDateRange.days, to: Date())!)
        let end = Self.isoFmt.string(from: Date())

        print("[Insights] 📡 Fetching: userId=\(userId) start=\(start) end=\(end) range=\(selectedDateRange.rawValue)")

        do {
            let response = try await APIService.shared.getExpenses(
                userId: userId,
                startDate: start,
                endDate: end,
                limit: 1000
            )
            allTransactions = response.transactions
            print("[Insights] ✅ Got \(response.transactions.count) transactions")
            for tx in response.transactions.prefix(10) {
                print("[Insights]   - \(tx.name) | $\(tx.amount) | cat=\(tx.subCategory) | date=\(tx.date ?? "nil") | src=\(tx.source ?? "nil")")
            }
            if response.transactions.count > 10 {
                print("[Insights]   ... and \(response.transactions.count - 10) more")
            }
            let chartEligible = response.transactions.filter { !$0.subCategory.isEmpty }
            print("[Insights] 📊 Chart-eligible (has category): \(chartEligible.count) of \(response.transactions.count)")
            saveToCache(for: selectedDateRange)
        } catch {
            errorMessage = "Unable to load spending data"
            print("[Insights] ❌ Error: \(error)")
        }
        isLoading = false
    }

    // MARK: - Private

    private static let isoFmt: DateFormatter = {
        let df = DateFormatter()
        df.dateFormat = "yyyy-MM-dd"
        return df
    }()
}
