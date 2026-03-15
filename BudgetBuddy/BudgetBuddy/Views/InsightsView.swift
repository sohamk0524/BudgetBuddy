//
//  InsightsView.swift
//  BudgetBuddy
//
//  Insights tab with interactive pie chart (spending by category) and
//  Screen Time-style bar chart (spending over time)
//

import SwiftUI
import Charts

@MainActor
struct InsightsView: View {
    @Bindable var viewModel: InsightsViewModel
    @Binding var selectedTab: Int

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 20) {
                    if viewModel.isLoading && viewModel.pieData.isEmpty {
                        loadingState
                    } else if viewModel.pieData.isEmpty && viewModel.barData.allSatisfy({ $0.amount == 0 }) {
                        emptyState
                    } else {
                        pieChartCard
                            .padding(.horizontal)

                        if viewModel.selectedPieCategory != nil {
                            categoryTransactionsCard
                                .padding(.horizontal)
                        }

                        barChartCard
                            .padding(.horizontal)
                    }
                }
                .padding(.vertical)
            }
            .background(Color.appBackground)
            .navigationTitle("Insights")
            .navigationBarTitleDisplayMode(.large)
            .toolbarColorScheme(.dark, for: .navigationBar)
            .task { await viewModel.fetchTransactions() }
            .refreshable { await viewModel.fetchTransactions() }
            .onAppear {
                Task { await viewModel.fetchTransactions() }
            }
            .onChange(of: selectedTab) { _, newTab in
                if newTab == 2 {
                    AnalyticsManager.logInsightsViewed()
                    Task { await viewModel.fetchTransactions() }
                }
            }
        }
    }

    // MARK: - Date Range Picker

    private var dateRangePicker: some View {
        HStack(spacing: 8) {
            ForEach(InsightsViewModel.DateRange.allCases) { range in
                Button {
                    viewModel.selectDateRange(range)
                    AnalyticsManager.logInsightsDateRangeChanged(range: range.rawValue)
                } label: {
                    Text(range.rawValue)
                        .font(.roundedCaption)
                        .fontWeight(.semibold)
                        .foregroundStyle(viewModel.selectedDateRange == range ? Color.appBackground : Color.textPrimary)
                        .padding(.horizontal, 16)
                        .padding(.vertical, 8)
                        .background(viewModel.selectedDateRange == range ? Color.accent : Color.surface)
                        .clipShape(Capsule())
                }
            }
            Spacer()
        }
    }

    // MARK: - Loading State

    private var loadingState: some View {
        VStack(spacing: 16) {
            ProgressView()
                .tint(Color.accent)
            Text("Loading insights...")
                .font(.roundedBody)
                .foregroundStyle(Color.textSecondary)
        }
        .frame(maxWidth: .infinity, minHeight: 300)
    }

    // MARK: - Empty State

    private var emptyState: some View {
        VStack(spacing: 16) {
            Image(systemName: "chart.pie")
                .font(.system(size: 48))
                .foregroundStyle(Color.textSecondary.opacity(0.5))

            Text("No Spending Data")
                .font(.roundedHeadline)
                .foregroundStyle(Color.textPrimary)

            Text("Classify your transactions in the Expenses tab to see insights here.")
                .font(.roundedBody)
                .foregroundStyle(Color.textSecondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 32)
        }
        .frame(maxWidth: .infinity, minHeight: 280)
    }

    // MARK: - Pie Chart Card

    private var pieChartCard: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Spending by Category")
                        .font(.roundedHeadline)
                        .foregroundStyle(Color.textPrimary)
                    Text(viewModel.selectedDateRange.label)
                        .font(.roundedCaption)
                        .foregroundStyle(Color.textSecondary)
                }
                Spacer()
                Text("$\(viewModel.totalSpending, specifier: "%.0f")")
                    .font(.rounded(.title2, weight: .bold))
                    .foregroundStyle(Color.accent)
                    .monospacedDigit()
            }

            // Donut chart
            Chart(viewModel.pieData) { slice in
                SectorMark(
                    angle: .value("Amount", slice.amount),
                    innerRadius: .ratio(0.6),
                    angularInset: 1.5
                )
                .foregroundStyle(slice.color)
                .opacity(viewModel.selectedPieCategory == nil || viewModel.selectedPieCategory == slice.category ? 1.0 : 0.3)
            }
            .chartAngleSelection(value: $pieAngleSelection)
            .onChange(of: pieAngleSelection) { _, newValue in
                guard let angle = newValue else { return }
                // chartAngleSelection returns cumulative value in data domain
                var cumulative = 0.0
                for slice in viewModel.pieData {
                    cumulative += slice.amount
                    if angle <= cumulative {
                        withAnimation(.easeInOut(duration: 0.2)) {
                            viewModel.togglePieCategory(slice.category)
                        }
                        AnalyticsManager.logInsightsCategoryTapped(category: slice.category)
                        pieAngleSelection = nil
                        return
                    }
                }
            }
            .frame(height: 220)
            .overlay {
                // Center label when a category is selected
                if let cat = viewModel.selectedPieCategory,
                   let slice = viewModel.pieData.first(where: { $0.category == cat }) {
                    VStack(spacing: 2) {
                        Image(systemName: slice.icon)
                            .font(.system(size: 18))
                            .foregroundStyle(slice.color)
                        Text("$\(slice.amount, specifier: "%.0f")")
                            .font(.rounded(.headline, weight: .bold))
                            .foregroundStyle(Color.textPrimary)
                            .monospacedDigit()
                        Text(slice.category.capitalized)
                            .font(.roundedCaption)
                            .foregroundStyle(Color.textSecondary)
                    }
                }
            }

            // Legend
            pieLegend
        }
        .walletCard()
    }

    @State private var pieAngleSelection: Double? = nil

    private var pieLegend: some View {
        let columns = [GridItem(.flexible()), GridItem(.flexible())]
        return LazyVGrid(columns: columns, alignment: .leading, spacing: 10) {
            ForEach(viewModel.pieData) { slice in
                Button {
                    viewModel.togglePieCategory(slice.category)
                    AnalyticsManager.logInsightsCategoryTapped(category: slice.category)
                } label: {
                    HStack(spacing: 8) {
                        Image(systemName: slice.icon)
                            .font(.system(size: 12))
                            .foregroundStyle(slice.color)
                            .frame(width: 20)

                        VStack(alignment: .leading, spacing: 1) {
                            Text(slice.category.capitalized)
                                .font(.roundedCaption)
                                .foregroundStyle(Color.textPrimary)
                            Text("$\(slice.amount, specifier: "%.0f")")
                                .font(.system(size: 11, weight: .semibold, design: .rounded))
                                .foregroundStyle(Color.textSecondary)
                                .monospacedDigit()
                        }

                        Spacer()

                        if viewModel.totalSpending > 0 {
                            Text("\(Int(slice.amount / viewModel.totalSpending * 100))%")
                                .font(.system(size: 11, weight: .bold, design: .rounded))
                                .foregroundStyle(slice.color)
                                .monospacedDigit()
                        }
                    }
                    .padding(.vertical, 4)
                    .opacity(viewModel.selectedPieCategory == nil || viewModel.selectedPieCategory == slice.category ? 1.0 : 0.4)
                }
                .buttonStyle(.plain)
            }
        }
    }

    // MARK: - Category Transactions Card

    private var categoryTransactionsCard: some View {
        VStack(alignment: .leading, spacing: 12) {
            if let cat = viewModel.selectedPieCategory {
                HStack {
                    Image(systemName: categoryIcon(for: cat))
                        .foregroundStyle(categoryColor(for: cat))
                    Text("\(cat.capitalized) Transactions")
                        .font(.roundedHeadline)
                        .foregroundStyle(Color.textPrimary)
                    Spacer()
                    Button {
                        withAnimation(.easeInOut(duration: 0.2)) {
                            viewModel.selectedPieCategory = nil
                        }
                    } label: {
                        Image(systemName: "xmark.circle.fill")
                            .foregroundStyle(Color.textSecondary)
                    }
                }

                let txns = viewModel.selectedCategoryTransactions
                if txns.isEmpty {
                    Text("No transactions in this category")
                        .font(.roundedCaption)
                        .foregroundStyle(Color.textSecondary)
                        .padding(.vertical, 8)
                } else {
                    ForEach(txns) { tx in
                        HStack(spacing: 12) {
                            VStack(alignment: .leading, spacing: 3) {
                                Text(tx.merchantName ?? tx.name)
                                    .font(.roundedBody)
                                    .foregroundStyle(Color.textPrimary)
                                    .lineLimit(1)
                                if let dateStr = tx.date {
                                    Text(insightsFormatDate(dateStr))
                                        .font(.roundedCaption)
                                        .foregroundStyle(Color.textSecondary)
                                }
                            }
                            Spacer()
                            Text("$\(abs(tx.amount), specifier: "%.2f")")
                                .font(.roundedBody)
                                .fontWeight(.medium)
                                .foregroundStyle(Color.textPrimary)
                                .monospacedDigit()
                        }
                        .padding(.vertical, 4)
                        if tx.id != txns.last?.id {
                            Divider().overlay(Color.textSecondary.opacity(0.2))
                        }
                    }
                }
            }
        }
        .walletCard()
    }

    // MARK: - Bar Chart Card (Screen Time Style)

    private var barChartCard: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                Text("Spending Over Time")
                    .font(.roundedHeadline)
                    .foregroundStyle(Color.textPrimary)
                Spacer()
            }

            // Daily / Weekly toggle
            HStack(spacing: 8) {
                ForEach(InsightsViewModel.BarGrouping.allCases) { grouping in
                    Button {
                        withAnimation(.easeInOut(duration: 0.2)) {
                            viewModel.barGrouping = grouping
                            viewModel.selectedBarDate = nil
                        }
                        AnalyticsManager.logInsightsBarGroupingChanged(grouping: grouping.rawValue)
                    } label: {
                        Text(grouping.rawValue)
                            .font(.roundedCaption)
                            .fontWeight(.semibold)
                            .foregroundStyle(viewModel.barGrouping == grouping ? Color.appBackground : Color.textPrimary)
                            .padding(.horizontal, 14)
                            .padding(.vertical, 6)
                            .background(viewModel.barGrouping == grouping ? Color.accent : Color.surface.opacity(0.6))
                            .clipShape(Capsule())
                    }
                }
                Spacer()
            }

            // Selected bar callout or average label
            if let selected = viewModel.selectedBarAmount {
                HStack(spacing: 6) {
                    Circle()
                        .fill(Color.accent)
                        .frame(width: 8, height: 8)
                    Text(selected.label)
                        .font(.roundedCaption)
                        .foregroundStyle(Color.textSecondary)
                    Text("$\(selected.amount, specifier: "%.2f")")
                        .font(.rounded(.headline, weight: .bold))
                        .foregroundStyle(Color.accent)
                        .monospacedDigit()
                }
                .transition(.opacity)
            } else if viewModel.barAverage > 0 {
                HStack(spacing: 4) {
                    Text("Average:")
                        .font(.roundedCaption)
                        .foregroundStyle(Color.textSecondary)
                    Text("$\(viewModel.barAverage, specifier: "%.0f") / \(viewModel.barGrouping == .daily ? "day" : "week")")
                        .font(.roundedCaption)
                        .fontWeight(.semibold)
                        .foregroundStyle(Color.textPrimary)
                        .monospacedDigit()
                }
            }

            let data = viewModel.barData

            if data.isEmpty || data.allSatisfy({ $0.amount == 0 }) {
                Text("No spending data for this period")
                    .font(.roundedCaption)
                    .foregroundStyle(Color.textSecondary)
                    .frame(maxWidth: .infinity, minHeight: 160, alignment: .center)
            } else {
                Chart {
                    ForEach(data) { entry in
                        BarMark(
                            x: .value("Date", entry.date, unit: viewModel.barGrouping == .daily ? .day : .weekOfYear),
                            y: .value("Amount", entry.amount)
                        )
                        .foregroundStyle(
                            viewModel.selectedBarDate != nil && Calendar.current.isDate(entry.date, inSameDayAs: viewModel.selectedBarDate!)
                                ? Color.accent
                                : Color.accent.opacity(0.5)
                        )
                        .cornerRadius(3)
                    }

                    if viewModel.barAverage > 0 {
                        RuleMark(y: .value("Average", viewModel.barAverage))
                            .foregroundStyle(Color.textSecondary.opacity(0.6))
                            .lineStyle(StrokeStyle(lineWidth: 1, dash: [5, 3]))
                    }
                }
                .chartXSelection(value: $viewModel.selectedBarDate)
                .chartXAxis {
                    AxisMarks(values: .stride(by: xAxisStride, count: xAxisStrideCount)) { _ in
                        AxisValueLabel(format: xAxisFormat)
                            .foregroundStyle(Color.textSecondary)
                    }
                }
                .chartYAxis {
                    AxisMarks(position: .leading) { value in
                        AxisGridLine()
                            .foregroundStyle(Color.textSecondary.opacity(0.15))
                        AxisValueLabel {
                            if let amount = value.as(Double.self) {
                                Text("$\(Int(amount))")
                                    .font(.system(size: 10, design: .rounded))
                                    .foregroundStyle(Color.textSecondary)
                            }
                        }
                    }
                }
                .frame(height: 200)
            }
        }
        .walletCard()
    }

    // MARK: - Bar Chart Axis Helpers

    private var xAxisStride: Calendar.Component {
        viewModel.barGrouping == .weekly ? .weekOfYear : .day
    }

    private var xAxisStrideCount: Int {
        if viewModel.barGrouping == .weekly { return 1 }
        return 1
    }

    private var xAxisFormat: Date.FormatStyle {
        if viewModel.barGrouping == .weekly {
            return .dateTime.month(.abbreviated).day()
        }
        return .dateTime.weekday(.abbreviated)
    }

    // MARK: - Date Formatter

    private func insightsFormatDate(_ dateStr: String) -> String {
        let iso = ISO8601DateFormatter()
        if let date = iso.date(from: dateStr) {
            let df = DateFormatter()
            df.dateFormat = "MMM d, yyyy"
            return df.string(from: date)
        }
        let df = DateFormatter()
        df.dateFormat = "yyyy-MM-dd"
        if let date = df.date(from: dateStr) {
            df.dateFormat = "MMM d, yyyy"
            return df.string(from: date)
        }
        return dateStr
    }
}

#Preview {
    InsightsView(viewModel: InsightsViewModel(), selectedTab: .constant(2))
}
