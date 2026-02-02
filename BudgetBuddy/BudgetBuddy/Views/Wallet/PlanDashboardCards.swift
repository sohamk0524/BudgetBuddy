//
//  PlanDashboardCards.swift
//  BudgetBuddy
//
//  Card components for the spending plan dashboard
//

import SwiftUI

// MARK: - Safe to Spend Card (Hero)

struct SafeToSpendCard: View {
    let amount: Double
    let daysRemaining: Int
    let budgetUsedPercent: Double

    private var progress: Double {
        // Calculate what percentage of the month has passed
        let calendar = Calendar.current
        let today = Date()
        let daysInMonth = calendar.range(of: .day, in: .month, for: today)?.count ?? 30
        let currentDay = calendar.component(.day, from: today)
        return Double(currentDay) / Double(daysInMonth)
    }

    var body: some View {
        VStack(spacing: 16) {
            HStack {
                Image(systemName: "dollarsign.circle.fill")
                    .foregroundStyle(Color.accent)
                Text("Safe to Spend")
                    .font(.roundedCaption)
                    .foregroundStyle(Color.textSecondary)
                Spacer()
            }

            // Main amount
            Text("$\(amount, specifier: "%.0f")")
                .font(.system(size: 48, weight: .bold, design: .rounded))
                .monospacedDigit()
                .foregroundStyle(Color.textPrimary)

            Text("After bills, goals & events")
                .font(.roundedCaption)
                .foregroundStyle(Color.textSecondary)

            // Progress ring
            ZStack {
                Circle()
                    .stroke(Color.surface, lineWidth: 8)
                    .frame(width: 80, height: 80)

                Circle()
                    .trim(from: 0, to: min(1 - (budgetUsedPercent / 100), 1))
                    .stroke(
                        budgetUsedPercent > 80 ? Color.danger : Color.accent,
                        style: StrokeStyle(lineWidth: 8, lineCap: .round)
                    )
                    .frame(width: 80, height: 80)
                    .rotationEffect(.degrees(-90))

                VStack(spacing: 2) {
                    Text("\(daysRemaining)")
                        .font(.roundedHeadline)
                        .foregroundStyle(Color.textPrimary)
                    Text("days")
                        .font(.system(.caption2, design: .rounded))
                        .foregroundStyle(Color.textSecondary)
                }
            }

            Text("\(Int(budgetUsedPercent))% of budget used")
                .font(.roundedCaption)
                .foregroundStyle(budgetUsedPercent > 80 ? Color.danger : Color.textSecondary)
        }
        .padding(20)
        .frame(maxWidth: .infinity)
        .background(Color.surface)
        .clipShape(RoundedRectangle(cornerRadius: 20))
    }
}

// MARK: - Budget Breakdown Card

struct BudgetBreakdownCard: View {
    let categories: [BudgetCategory]
    let totalIncome: Double

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                Image(systemName: "chart.pie.fill")
                    .foregroundStyle(Color.accent)
                Text("Budget Breakdown")
                    .font(.roundedCaption)
                    .foregroundStyle(Color.textSecondary)
                Spacer()
            }

            // Donut chart
            DonutChartView(categories: categories)
                .frame(height: 120)

            // Category list
            VStack(spacing: 8) {
                ForEach(categories) { category in
                    HStack {
                        Circle()
                            .fill(Color(hex: category.color))
                            .frame(width: 8, height: 8)

                        Text(category.name)
                            .font(.roundedCaption)
                            .foregroundStyle(Color.textPrimary)

                        Spacer()

                        Text("$\(category.amount, specifier: "%.0f")")
                            .font(.roundedCaption)
                            .monospacedDigit()
                            .foregroundStyle(Color.textSecondary)
                    }
                }
            }
        }
        .padding(20)
        .frame(maxWidth: .infinity)
        .background(Color.surface)
        .clipShape(RoundedRectangle(cornerRadius: 20))
    }
}

// MARK: - Donut Chart View

struct DonutChartView: View {
    let categories: [BudgetCategory]

    private var total: Double {
        categories.reduce(0) { $0 + $1.amount }
    }

    var body: some View {
        GeometryReader { geometry in
            let size = min(geometry.size.width, geometry.size.height)

            ZStack {
                ForEach(Array(categories.enumerated()), id: \.element.id) { index, category in
                    let startAngle = startAngle(for: index)
                    let endAngle = endAngle(for: index)

                    Circle()
                        .trim(from: startAngle / 360, to: endAngle / 360)
                        .stroke(
                            Color(hex: category.color),
                            style: StrokeStyle(lineWidth: size * 0.15, lineCap: .butt)
                        )
                        .rotationEffect(.degrees(-90))
                }

                VStack(spacing: 2) {
                    Text("$\(total, specifier: "%.0f")")
                        .font(.roundedHeadline)
                        .monospacedDigit()
                        .foregroundStyle(Color.textPrimary)
                    Text("total")
                        .font(.system(.caption2, design: .rounded))
                        .foregroundStyle(Color.textSecondary)
                }
            }
            .frame(width: size, height: size)
            .position(x: geometry.size.width / 2, y: geometry.size.height / 2)
        }
    }

    private func startAngle(for index: Int) -> Double {
        guard total > 0 else { return 0 }
        let preceding = categories.prefix(index).reduce(0) { $0 + $1.amount }
        return (preceding / total) * 360
    }

    private func endAngle(for index: Int) -> Double {
        guard total > 0 else { return 0 }
        let including = categories.prefix(index + 1).reduce(0) { $0 + $1.amount }
        return (including / total) * 360
    }
}

// MARK: - Savings Progress Card

struct SavingsProgressCard: View {
    let plan: SpendingPlan

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                Image(systemName: "target")
                    .foregroundStyle(Color.accent)
                Text("Savings Goals")
                    .font(.roundedCaption)
                    .foregroundStyle(Color.textSecondary)
                Spacer()
            }

            // Show savings category items
            if let savingsCategory = plan.categoryAllocations.first(where: { $0.id == "savings" }),
               let items = savingsCategory.items {
                ForEach(items, id: \.name) { item in
                    VStack(alignment: .leading, spacing: 8) {
                        HStack {
                            Text(item.name)
                                .font(.roundedBody)
                                .foregroundStyle(Color.textPrimary)

                            Spacer()

                            Text("$\(item.amount, specifier: "%.0f")/mo")
                                .font(.roundedCaption)
                                .monospacedDigit()
                                .foregroundStyle(Color.accent)
                        }

                        // Progress bar placeholder
                        GeometryReader { geometry in
                            ZStack(alignment: .leading) {
                                RoundedRectangle(cornerRadius: 4)
                                    .fill(Color.appBackground)
                                    .frame(height: 8)

                                RoundedRectangle(cornerRadius: 4)
                                    .fill(Color.accent)
                                    .frame(width: geometry.size.width * 0.5, height: 8)
                            }
                        }
                        .frame(height: 8)
                    }
                }
            } else {
                Text("No savings goals set")
                    .font(.roundedCaption)
                    .foregroundStyle(Color.textSecondary)
            }
        }
        .padding(20)
        .frame(maxWidth: .infinity)
        .background(Color.surface)
        .clipShape(RoundedRectangle(cornerRadius: 20))
    }
}

// MARK: - Recommendations Card

struct RecommendationsCard: View {
    let recommendations: [Recommendation]

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                Image(systemName: "lightbulb.fill")
                    .foregroundStyle(Color.accent)
                Text("Smart Insights")
                    .font(.roundedCaption)
                    .foregroundStyle(Color.textSecondary)
                Spacer()
            }

            if recommendations.isEmpty {
                Text("Your budget looks healthy!")
                    .font(.roundedBody)
                    .foregroundStyle(Color.textSecondary)
            } else {
                VStack(alignment: .leading, spacing: 12) {
                    ForEach(recommendations.prefix(3)) { rec in
                        VStack(alignment: .leading, spacing: 4) {
                            Text(rec.title)
                                .font(.roundedHeadline)
                                .foregroundStyle(Color.textPrimary)

                            Text(rec.description)
                                .font(.roundedCaption)
                                .foregroundStyle(Color.textSecondary)
                                .lineLimit(2)

                            if let savings = rec.potentialSavings, savings > 0 {
                                Text("Potential savings: $\(savings, specifier: "%.0f")/mo")
                                    .font(.roundedCaption)
                                    .foregroundStyle(Color.accent)
                            }
                        }
                        .padding(12)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .background(Color.appBackground)
                        .clipShape(RoundedRectangle(cornerRadius: 12))
                    }
                }
            }
        }
        .padding(20)
        .frame(maxWidth: .infinity)
        .background(Color.surface)
        .clipShape(RoundedRectangle(cornerRadius: 20))
    }
}

// MARK: - Generate Plan Card (CTA)

struct GeneratePlanCard: View {
    let action: () -> Void

    var body: some View {
        VStack(spacing: 20) {
            Image(systemName: "wand.and.stars")
                .font(.system(size: 48))
                .foregroundStyle(Color.accent)

            VStack(spacing: 8) {
                Text("Generate Your Plan")
                    .font(.roundedTitle)
                    .foregroundStyle(Color.textPrimary)

                Text("Answer a few questions to create your personalized spending plan")
                    .font(.roundedBody)
                    .foregroundStyle(Color.textSecondary)
                    .multilineTextAlignment(.center)
            }

            Button(action: action) {
                Text("Get Started")
                    .font(.roundedHeadline)
                    .foregroundStyle(Color.appBackground)
                    .frame(maxWidth: .infinity)
                    .padding()
            }
            .background(Color.accent)
            .clipShape(RoundedRectangle(cornerRadius: 12))
        }
        .padding(24)
        .frame(maxWidth: .infinity)
        .background(Color.surface)
        .clipShape(RoundedRectangle(cornerRadius: 20))
    }
}

// MARK: - Previews

#Preview("Safe to Spend") {
    SafeToSpendCard(amount: 847, daysRemaining: 12, budgetUsedPercent: 55)
        .padding()
        .background(Color.appBackground)
}

#Preview("Budget Breakdown") {
    BudgetBreakdownCard(
        categories: [
            BudgetCategory(id: "fixed", name: "Fixed", amount: 1450, color: "#FF6B6B", items: nil),
            BudgetCategory(id: "flexible", name: "Flexible", amount: 600, color: "#4ECDC4", items: nil),
            BudgetCategory(id: "discretionary", name: "Discretionary", amount: 300, color: "#45B7D1", items: nil)
        ],
        totalIncome: 3500
    )
    .padding()
    .background(Color.appBackground)
}

#Preview("Generate Plan CTA") {
    GeneratePlanCard { }
        .padding()
        .background(Color.appBackground)
}
