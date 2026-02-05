//
//  GenerativeWidgetView.swift
//  BudgetBuddy
//
//  A wrapper view that renders the appropriate widget based on VisualComponent type
//

import SwiftUI

struct GenerativeWidgetView: View {
    let component: VisualComponent

    var body: some View {
        Group {
            switch component {
            case .burndownChart(let spent, let budget, let idealPace):
                BurndownWidgetView(spent: spent, budget: budget, idealPace: idealPace)

            case .budgetSlider(let category, let current, let max):
                BudgetSliderView(category: category, current: current, max: max)

            case .budgetBurndown(let data):
                // Legacy burndown chart with data points
                LegacyBurndownView(data: data)

            case .interactiveSlider(let category, let current, let max):
                BudgetSliderView(category: category, current: current, max: max)

            case .sankeyFlow:
                PlaceholderView(title: "Cash Flow Diagram", message: "Sankey flow visualization coming soon")

            case .spendingPlan(let safeToSpend, let categories):
                SpendingPlanWidgetView(safeToSpend: safeToSpend, categories: categories)

            // Phase 2: New Visual Components
            case .comparisonChart(let data):
                ComparisonChartWidgetView(data: data)

            case .goalProgress(let data):
                GoalProgressWidgetView(data: data)

            case .transactionList(let data):
                TransactionListWidgetView(data: data)

            case .actionCard(let data):
                ActionCardWidgetView(data: data)

            case .categoryBreakdown(let data):
                CategoryBreakdownWidgetView(data: data)

            case .insightCard(let data):
                InsightCardWidgetView(data: data)
            }
        }
        .cardStyle()
    }
}

// MARK: - Budget Slider View

struct BudgetSliderView: View {
    let category: String
    let current: Double
    let max: Double

    @State private var sliderValue: Double

    init(category: String, current: Double, max: Double) {
        self.category = category
        self.current = current
        self.max = max
        self._sliderValue = State(initialValue: current)
    }

    private var percentage: Double {
        (sliderValue / max) * 100
    }

    private var isOverBudget: Bool {
        sliderValue > max * 0.8
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text(category)
                    .font(.roundedHeadline)
                    .foregroundStyle(Color.textPrimary)

                Spacer()

                Text("$\(Int(sliderValue)) / $\(Int(max))")
                    .font(.roundedCaption)
                    .monospacedDigit()
                    .foregroundStyle(isOverBudget ? Color.danger : Color.textSecondary)
            }

            // Progress bar
            GeometryReader { geometry in
                ZStack(alignment: .leading) {
                    // Background track
                    RoundedRectangle(cornerRadius: 4)
                        .fill(Color.appBackground)
                        .frame(height: 8)

                    // Fill
                    RoundedRectangle(cornerRadius: 4)
                        .fill(isOverBudget ? Color.danger : Color.accent)
                        .frame(width: min(geometry.size.width * (sliderValue / max), geometry.size.width), height: 8)
                }
            }
            .frame(height: 8)

            // Percentage label
            Text("\(Int(percentage))% of budget used")
                .font(.roundedCaption)
                .foregroundStyle(Color.textSecondary)
        }
        .padding()
    }
}

// MARK: - Legacy Burndown View (for data-point based charts)

struct LegacyBurndownView: View {
    let data: [BurndownDataPoint]

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Budget Burndown")
                .font(.roundedHeadline)
                .foregroundStyle(Color.textPrimary)

            if let first = data.first, let last = data.last {
                HStack {
                    VStack(alignment: .leading) {
                        Text("Start")
                            .font(.roundedCaption)
                            .foregroundStyle(Color.textSecondary)
                        Text("$\(Int(first.amount))")
                            .font(.rounded(.title3, weight: .semibold))
                            .monospacedDigit()
                            .foregroundStyle(Color.textPrimary)
                    }

                    Spacer()

                    VStack(alignment: .trailing) {
                        Text("End")
                            .font(.roundedCaption)
                            .foregroundStyle(Color.textSecondary)
                        Text("$\(Int(last.amount))")
                            .font(.rounded(.title3, weight: .semibold))
                            .monospacedDigit()
                            .foregroundStyle(last.amount > 0 ? Color.accent : Color.danger)
                    }
                }
            }

            Text("\(data.count) days tracked")
                .font(.roundedCaption)
                .foregroundStyle(Color.textSecondary)
        }
        .padding()
    }
}

// MARK: - Spending Plan Widget View

struct SpendingPlanWidgetView: View {
    let safeToSpend: Double
    let categories: [BudgetCategory]

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Your Spending Plan")
                .font(.roundedHeadline)
                .foregroundStyle(Color.textPrimary)

            HStack {
                Text("Safe to Spend:")
                    .font(.roundedBody)
                    .foregroundStyle(Color.textSecondary)

                Spacer()

                Text("$\(Int(safeToSpend))")
                    .font(.roundedTitle)
                    .monospacedDigit()
                    .foregroundStyle(Color.accent)
            }

            Divider()
                .background(Color.textSecondary.opacity(0.3))

            ForEach(categories.prefix(4)) { category in
                HStack {
                    Circle()
                        .fill(Color(hex: category.color))
                        .frame(width: 8, height: 8)

                    Text(category.name)
                        .font(.roundedCaption)
                        .foregroundStyle(Color.textPrimary)

                    Spacer()

                    Text("$\(Int(category.amount))")
                        .font(.roundedCaption)
                        .monospacedDigit()
                        .foregroundStyle(Color.textSecondary)
                }
            }
        }
        .padding()
    }
}

// MARK: - Placeholder View

struct PlaceholderView: View {
    let title: String
    let message: String

    var body: some View {
        VStack(spacing: 12) {
            Image(systemName: "chart.bar.xaxis")
                .font(.system(size: 32))
                .foregroundStyle(Color.textSecondary)

            Text(title)
                .font(.roundedHeadline)
                .foregroundStyle(Color.textPrimary)

            Text(message)
                .font(.roundedCaption)
                .foregroundStyle(Color.textSecondary)
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity)
        .padding()
    }
}

// MARK: - Comparison Chart Widget

struct ComparisonChartWidgetView: View {
    let data: ComparisonChartData

    private var changeColor: Color {
        data.changePercent > 0 ? Color.danger : Color.accent
    }

    private var changeIcon: String {
        data.changePercent > 0 ? "arrow.up.right" : "arrow.down.right"
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Spending Comparison")
                .font(.roundedHeadline)
                .foregroundStyle(Color.textPrimary)

            HStack(spacing: 20) {
                // Current Period
                VStack(alignment: .leading, spacing: 4) {
                    Text(data.currentPeriod.label)
                        .font(.roundedCaption)
                        .foregroundStyle(Color.textSecondary)
                    Text("$\(Int(data.currentPeriod.total))")
                        .font(.rounded(.title2, weight: .bold))
                        .monospacedDigit()
                        .foregroundStyle(Color.textPrimary)
                }

                Spacer()

                // Change indicator
                HStack(spacing: 4) {
                    Image(systemName: changeIcon)
                        .font(.system(size: 12, weight: .semibold))
                    Text("\(abs(Int(data.changePercent)))%")
                        .font(.rounded(.subheadline, weight: .semibold))
                        .monospacedDigit()
                }
                .foregroundStyle(changeColor)
                .padding(.horizontal, 10)
                .padding(.vertical, 6)
                .background(changeColor.opacity(0.15))
                .clipShape(Capsule())

                Spacer()

                // Previous Period
                VStack(alignment: .trailing, spacing: 4) {
                    Text(data.previousPeriod.label)
                        .font(.roundedCaption)
                        .foregroundStyle(Color.textSecondary)
                    Text("$\(Int(data.previousPeriod.total))")
                        .font(.rounded(.title2, weight: .bold))
                        .monospacedDigit()
                        .foregroundStyle(Color.textSecondary)
                }
            }

            // Comparison bars
            GeometryReader { geometry in
                let maxValue = max(data.currentPeriod.total, data.previousPeriod.total)
                let currentWidth = maxValue > 0 ? (data.currentPeriod.total / maxValue) * geometry.size.width : 0
                let previousWidth = maxValue > 0 ? (data.previousPeriod.total / maxValue) * geometry.size.width : 0

                VStack(spacing: 8) {
                    RoundedRectangle(cornerRadius: 4)
                        .fill(Color.accent)
                        .frame(width: currentWidth, height: 12)
                        .frame(maxWidth: .infinity, alignment: .leading)

                    RoundedRectangle(cornerRadius: 4)
                        .fill(Color.textSecondary.opacity(0.5))
                        .frame(width: previousWidth, height: 12)
                        .frame(maxWidth: .infinity, alignment: .leading)
                }
            }
            .frame(height: 32)

            // Category breakdown if available
            if let categories = data.categories, !categories.isEmpty {
                Divider()
                    .background(Color.textSecondary.opacity(0.3))

                ForEach(categories.prefix(3)) { category in
                    HStack {
                        Text(category.name)
                            .font(.roundedCaption)
                            .foregroundStyle(Color.textPrimary)
                        Spacer()
                        Text("$\(Int(category.current))")
                            .font(.roundedCaption)
                            .monospacedDigit()
                            .foregroundStyle(Color.textSecondary)
                    }
                }
            }
        }
        .padding()
    }
}

// MARK: - Goal Progress Widget

struct GoalProgressWidgetView: View {
    let data: GoalProgressData

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                Text("Savings Goals")
                    .font(.roundedHeadline)
                    .foregroundStyle(Color.textPrimary)

                Spacer()

                Text("\(Int(data.overallProgress))%")
                    .font(.rounded(.subheadline, weight: .semibold))
                    .monospacedDigit()
                    .foregroundStyle(Color.accent)
            }

            // Overall progress bar
            GeometryReader { geometry in
                ZStack(alignment: .leading) {
                    RoundedRectangle(cornerRadius: 6)
                        .fill(Color.appBackground)
                        .frame(height: 12)

                    RoundedRectangle(cornerRadius: 6)
                        .fill(Color.accent)
                        .frame(width: geometry.size.width * min(data.overallProgress / 100, 1.0), height: 12)
                }
            }
            .frame(height: 12)

            // Totals
            HStack {
                VStack(alignment: .leading) {
                    Text("Saved")
                        .font(.roundedCaption)
                        .foregroundStyle(Color.textSecondary)
                    Text("$\(Int(data.totalCurrent))")
                        .font(.rounded(.title3, weight: .semibold))
                        .monospacedDigit()
                        .foregroundStyle(Color.accent)
                }

                Spacer()

                VStack(alignment: .trailing) {
                    Text("Target")
                        .font(.roundedCaption)
                        .foregroundStyle(Color.textSecondary)
                    Text("$\(Int(data.totalTarget))")
                        .font(.rounded(.title3, weight: .semibold))
                        .monospacedDigit()
                        .foregroundStyle(Color.textPrimary)
                }
            }

            if !data.goals.isEmpty {
                Divider()
                    .background(Color.textSecondary.opacity(0.3))

                ForEach(data.goals.prefix(4)) { goal in
                    GoalRowView(goal: goal)
                }
            }
        }
        .padding()
    }
}

struct GoalRowView: View {
    let goal: GoalProgressItem

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                if let icon = goal.icon {
                    Text(icon)
                        .font(.system(size: 14))
                }
                Text(goal.name)
                    .font(.roundedCaption)
                    .foregroundStyle(Color.textPrimary)

                Spacer()

                Text("$\(Int(goal.current)) / $\(Int(goal.target))")
                    .font(.roundedCaption)
                    .monospacedDigit()
                    .foregroundStyle(Color.textSecondary)
            }

            GeometryReader { geometry in
                ZStack(alignment: .leading) {
                    RoundedRectangle(cornerRadius: 3)
                        .fill(Color.appBackground)
                        .frame(height: 6)

                    RoundedRectangle(cornerRadius: 3)
                        .fill(goal.color != nil ? Color(hex: goal.color!) : Color.accent)
                        .frame(width: geometry.size.width * min(goal.progressPercent / 100, 1.0), height: 6)
                }
            }
            .frame(height: 6)
        }
    }
}

// MARK: - Transaction List Widget

struct TransactionListWidgetView: View {
    let data: TransactionListData

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("Transactions")
                    .font(.roundedHeadline)
                    .foregroundStyle(Color.textPrimary)

                Spacer()

                Text("\(data.summary.count) items")
                    .font(.roundedCaption)
                    .foregroundStyle(Color.textSecondary)
            }

            // Summary
            HStack(spacing: 16) {
                VStack(alignment: .leading) {
                    Text("Income")
                        .font(.roundedCaption)
                        .foregroundStyle(Color.textSecondary)
                    Text("+$\(Int(data.summary.totalIncome))")
                        .font(.rounded(.subheadline, weight: .semibold))
                        .monospacedDigit()
                        .foregroundStyle(Color.accent)
                }

                Spacer()

                VStack(alignment: .trailing) {
                    Text("Expenses")
                        .font(.roundedCaption)
                        .foregroundStyle(Color.textSecondary)
                    Text("-$\(Int(data.summary.totalExpenses))")
                        .font(.rounded(.subheadline, weight: .semibold))
                        .monospacedDigit()
                        .foregroundStyle(Color.danger)
                }
            }

            Divider()
                .background(Color.textSecondary.opacity(0.3))

            // Transaction list
            ForEach(data.transactions.prefix(5)) { transaction in
                TransactionRowView(transaction: transaction)
            }

            if data.transactions.count > 5 {
                Text("+ \(data.transactions.count - 5) more")
                    .font(.roundedCaption)
                    .foregroundStyle(Color.accent)
                    .frame(maxWidth: .infinity, alignment: .center)
            }
        }
        .padding()
    }
}

struct TransactionRowView: View {
    let transaction: TransactionItem

    private var categoryIcon: String {
        switch transaction.category.lowercased() {
        case "groceries", "food": return "cart.fill"
        case "dining", "restaurant": return "fork.knife"
        case "transport", "transportation": return "car.fill"
        case "entertainment": return "tv.fill"
        case "shopping": return "bag.fill"
        case "utilities": return "bolt.fill"
        case "health": return "heart.fill"
        default: return "dollarsign.circle.fill"
        }
    }

    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: categoryIcon)
                .font(.system(size: 14))
                .foregroundStyle(transaction.isExpense ? Color.danger : Color.accent)
                .frame(width: 28, height: 28)
                .background(transaction.isExpense ? Color.danger.opacity(0.15) : Color.accent.opacity(0.15))
                .clipShape(Circle())

            VStack(alignment: .leading, spacing: 2) {
                Text(transaction.description)
                    .font(.roundedCaption)
                    .foregroundStyle(Color.textPrimary)
                    .lineLimit(1)

                if let merchant = transaction.merchant {
                    Text(merchant)
                        .font(.system(size: 10, design: .rounded))
                        .foregroundStyle(Color.textSecondary)
                }
            }

            Spacer()

            Text("\(transaction.isExpense ? "-" : "+")$\(Int(abs(transaction.amount)))")
                .font(.rounded(.subheadline, weight: .medium))
                .monospacedDigit()
                .foregroundStyle(transaction.isExpense ? Color.danger : Color.accent)
        }
    }
}

// MARK: - Action Card Widget

struct ActionCardWidgetView: View {
    let data: ActionCardData

    private var severityColor: Color {
        switch data.severity.lowercased() {
        case "warning": return Color(hex: "#F59E0B")  // Amber
        case "error", "danger": return Color.danger
        case "success": return Color.accent
        default: return Color.accent  // info
        }
    }

    private var severityIcon: String {
        switch data.severity.lowercased() {
        case "warning": return "exclamationmark.triangle.fill"
        case "error", "danger": return "xmark.circle.fill"
        case "success": return "checkmark.circle.fill"
        default: return "info.circle.fill"
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 10) {
                if let icon = data.icon {
                    Text(icon)
                        .font(.system(size: 24))
                } else {
                    Image(systemName: severityIcon)
                        .font(.system(size: 20))
                        .foregroundStyle(severityColor)
                }

                Text(data.title)
                    .font(.roundedHeadline)
                    .foregroundStyle(Color.textPrimary)

                Spacer()
            }

            Text(data.message)
                .font(.roundedBody)
                .foregroundStyle(Color.textSecondary)
                .fixedSize(horizontal: false, vertical: true)

            if !data.actions.isEmpty {
                HStack(spacing: 10) {
                    ForEach(data.actions) { action in
                        ActionButtonView(action: action)
                    }
                }
            }
        }
        .padding()
        .overlay(
            RoundedRectangle(cornerRadius: 16)
                .stroke(severityColor.opacity(0.3), lineWidth: 1)
        )
    }
}

struct ActionButtonView: View {
    let action: ActionButton

    private var buttonStyle: (bg: Color, fg: Color) {
        switch action.style.lowercased() {
        case "primary": return (Color.accent, Color.appBackground)
        case "danger": return (Color.danger, Color.white)
        default: return (Color.surface, Color.textPrimary)  // secondary
        }
    }

    var body: some View {
        Text(action.label)
            .font(.rounded(.subheadline, weight: .semibold))
            .foregroundStyle(buttonStyle.fg)
            .padding(.horizontal, 16)
            .padding(.vertical, 8)
            .background(buttonStyle.bg)
            .clipShape(Capsule())
    }
}

// MARK: - Category Breakdown Widget (Pie/Donut Chart)

struct CategoryBreakdownWidgetView: View {
    let data: CategoryBreakdownData

    private let defaultColors = ["#2DD4BF", "#F43F5E", "#8B5CF6", "#F59E0B", "#3B82F6", "#EC4899"]

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                Text("Spending by Category")
                    .font(.roundedHeadline)
                    .foregroundStyle(Color.textPrimary)

                Spacer()

                Text("$\(Int(data.total))")
                    .font(.rounded(.subheadline, weight: .semibold))
                    .monospacedDigit()
                    .foregroundStyle(Color.textSecondary)
            }

            // Simple donut chart representation
            HStack(spacing: 20) {
                // Donut chart
                ZStack {
                    ForEach(Array(data.categories.prefix(6).enumerated()), id: \.element.id) { index, category in
                        let startAngle = startAngle(for: index)
                        let endAngle = endAngle(for: index)
                        let color = category.color != nil ? Color(hex: category.color!) : Color(hex: defaultColors[index % defaultColors.count])

                        DonutSegment(startAngle: startAngle, endAngle: endAngle)
                            .stroke(color, lineWidth: 16)
                    }

                    // Center text
                    VStack(spacing: 0) {
                        Text("\(data.categories.count)")
                            .font(.rounded(.title2, weight: .bold))
                            .foregroundStyle(Color.textPrimary)
                        Text("categories")
                            .font(.system(size: 10, design: .rounded))
                            .foregroundStyle(Color.textSecondary)
                    }
                }
                .frame(width: 100, height: 100)

                // Legend
                VStack(alignment: .leading, spacing: 6) {
                    ForEach(Array(data.categories.prefix(5).enumerated()), id: \.element.id) { index, category in
                        HStack(spacing: 8) {
                            Circle()
                                .fill(category.color != nil ? Color(hex: category.color!) : Color(hex: defaultColors[index % defaultColors.count]))
                                .frame(width: 8, height: 8)

                            Text(category.name)
                                .font(.roundedCaption)
                                .foregroundStyle(Color.textPrimary)
                                .lineLimit(1)

                            Spacer()

                            Text("\(Int(category.percent))%")
                                .font(.roundedCaption)
                                .monospacedDigit()
                                .foregroundStyle(Color.textSecondary)
                        }
                    }
                }
            }
        }
        .padding()
    }

    private func startAngle(for index: Int) -> Angle {
        let precedingPercent = data.categories.prefix(index).reduce(0) { $0 + $1.percent }
        return Angle(degrees: precedingPercent * 3.6 - 90)
    }

    private func endAngle(for index: Int) -> Angle {
        let totalPercent = data.categories.prefix(index + 1).reduce(0) { $0 + $1.percent }
        return Angle(degrees: totalPercent * 3.6 - 90)
    }
}

struct DonutSegment: Shape {
    let startAngle: Angle
    let endAngle: Angle

    func path(in rect: CGRect) -> Path {
        var path = Path()
        let center = CGPoint(x: rect.midX, y: rect.midY)
        let radius = min(rect.width, rect.height) / 2 - 8

        path.addArc(center: center, radius: radius, startAngle: startAngle, endAngle: endAngle, clockwise: false)

        return path
    }
}

// MARK: - Insight Card Widget

struct InsightCardWidgetView: View {
    let data: InsightCardData

    private var trendIcon: String {
        switch data.trend?.lowercased() {
        case "up": return "arrow.up.right.circle.fill"
        case "down": return "arrow.down.right.circle.fill"
        default: return "minus.circle.fill"
        }
    }

    private var trendColor: Color {
        switch data.trend?.lowercased() {
        case "up": return Color.danger
        case "down": return Color.accent
        default: return Color.textSecondary
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: "lightbulb.fill")
                    .font(.system(size: 16))
                    .foregroundStyle(Color(hex: "#F59E0B"))

                Text(data.title)
                    .font(.roundedHeadline)
                    .foregroundStyle(Color.textPrimary)

                Spacer()

                if data.trend != nil {
                    Image(systemName: trendIcon)
                        .font(.system(size: 16))
                        .foregroundStyle(trendColor)
                }
            }

            Text(data.insight)
                .font(.roundedBody)
                .foregroundStyle(Color.textSecondary)
                .fixedSize(horizontal: false, vertical: true)

            // Data points if available
            if let dataPoints = data.dataPoints, !dataPoints.isEmpty {
                HStack(spacing: 16) {
                    ForEach(dataPoints.prefix(3)) { point in
                        VStack(spacing: 2) {
                            Text(point.value)
                                .font(.rounded(.subheadline, weight: .semibold))
                                .monospacedDigit()
                                .foregroundStyle(Color.textPrimary)
                            Text(point.label)
                                .font(.system(size: 10, design: .rounded))
                                .foregroundStyle(Color.textSecondary)
                        }
                    }
                }
            }

            // Recommendation if available
            if let recommendation = data.recommendation {
                HStack(spacing: 8) {
                    Image(systemName: "arrow.right.circle.fill")
                        .font(.system(size: 14))
                        .foregroundStyle(Color.accent)

                    Text(recommendation)
                        .font(.roundedCaption)
                        .foregroundStyle(Color.accent)
                }
                .padding(.top, 4)
            }
        }
        .padding()
        .background(
            LinearGradient(
                gradient: Gradient(colors: [Color(hex: "#F59E0B").opacity(0.1), Color.clear]),
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
        )
        .clipShape(RoundedRectangle(cornerRadius: 16))
    }
}

// MARK: - Preview

#Preview("All Widgets") {
    ScrollView {
        VStack(spacing: 16) {
            GenerativeWidgetView(component: .burndownChart(spent: 1876, budget: 2500, idealPace: 1450))

            GenerativeWidgetView(component: .budgetSlider(category: "Groceries", current: 280, max: 400))

            GenerativeWidgetView(component: .comparisonChart(data: ComparisonChartData(
                currentPeriod: PeriodData(label: "This Month", total: 2450, startDate: nil, endDate: nil),
                previousPeriod: PeriodData(label: "Last Month", total: 2100, startDate: nil, endDate: nil),
                categories: [
                    CategoryComparison(name: "Groceries", current: 450, previous: 380),
                    CategoryComparison(name: "Dining", current: 320, previous: 280)
                ],
                changePercent: 16.7
            )))

            GenerativeWidgetView(component: .goalProgress(data: GoalProgressData(
                goals: [
                    GoalProgressItem(name: "Emergency Fund", current: 2500, target: 5000, progressPercent: 50, remaining: 2500, icon: "🏦", color: "#2DD4BF"),
                    GoalProgressItem(name: "Vacation", current: 800, target: 2000, progressPercent: 40, remaining: 1200, icon: "✈️", color: "#8B5CF6")
                ],
                totalCurrent: 3300,
                totalTarget: 7000,
                overallProgress: 47.1
            )))

            GenerativeWidgetView(component: .categoryBreakdown(data: CategoryBreakdownData(
                categories: [
                    CategoryBreakdownItem(name: "Housing", amount: 1200, percent: 40, color: "#2DD4BF"),
                    CategoryBreakdownItem(name: "Food", amount: 600, percent: 20, color: "#F43F5E"),
                    CategoryBreakdownItem(name: "Transport", amount: 300, percent: 10, color: "#8B5CF6"),
                    CategoryBreakdownItem(name: "Entertainment", amount: 250, percent: 8.3, color: "#F59E0B"),
                    CategoryBreakdownItem(name: "Other", amount: 650, percent: 21.7, color: "#3B82F6")
                ],
                total: 3000
            )))

            GenerativeWidgetView(component: .insightCard(data: InsightCardData(
                title: "Spending Trend",
                insight: "Your dining expenses increased by 15% this month compared to your 3-month average.",
                dataPoints: [
                    InsightDataPoint(label: "This Month", value: "$320"),
                    InsightDataPoint(label: "Average", value: "$278")
                ],
                trend: "up",
                recommendation: "Consider meal prepping to reduce dining costs"
            )))

            GenerativeWidgetView(component: .actionCard(data: ActionCardData(
                title: "Budget Alert",
                message: "You've used 85% of your Entertainment budget with 10 days remaining.",
                actions: [
                    ActionButton(label: "View Details", action: "view_budget", style: "primary", data: nil),
                    ActionButton(label: "Adjust", action: "adjust_budget", style: "secondary", data: nil)
                ],
                icon: nil,
                severity: "warning"
            )))

            GenerativeWidgetView(component: .transactionList(data: TransactionListData(
                transactions: [
                    TransactionItem(id: "1", description: "Whole Foods", amount: 87.50, isExpense: true, category: "groceries", date: "2026-02-04", merchant: "Whole Foods Market", icon: nil),
                    TransactionItem(id: "2", description: "Salary Deposit", amount: 3500, isExpense: false, category: "income", date: "2026-02-01", merchant: "Employer Inc", icon: nil),
                    TransactionItem(id: "3", description: "Netflix", amount: 15.99, isExpense: true, category: "entertainment", date: "2026-02-03", merchant: "Netflix", icon: nil)
                ],
                filters: nil,
                summary: TransactionSummary(totalIncome: 3500, totalExpenses: 103.49, count: 3)
            )))
        }
        .padding()
    }
    .background(Color.appBackground)
}
