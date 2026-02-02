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

// MARK: - Preview

#Preview {
    ScrollView {
        VStack(spacing: 16) {
            GenerativeWidgetView(component: .burndownChart(spent: 1876, budget: 2500, idealPace: 1450))

            GenerativeWidgetView(component: .budgetSlider(category: "Groceries", current: 280, max: 400))

            GenerativeWidgetView(component: .sankeyFlow(nodes: []))
        }
        .padding()
    }
    .background(Color.appBackground)
}
