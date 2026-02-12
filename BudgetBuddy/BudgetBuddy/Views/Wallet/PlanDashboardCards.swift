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

// MARK: - Spending Progress Card

struct SpendingProgressCard: View {
    let disposableIncome: Double  // Income minus fixed expenses
    let amountSpent: Double       // Variable spending so far
    let daysRemaining: Int

    private var percentSpent: Double {
        guard disposableIncome > 0 else { return 0 }
        return (amountSpent / disposableIncome) * 100
    }

    private var remaining: Double {
        disposableIncome - amountSpent
    }

    private var isOverBudget: Bool {
        amountSpent > disposableIncome
    }

    private var isWarning: Bool {
        percentSpent >= 75 && !isOverBudget
    }

    private var progressColor: Color {
        if isOverBudget {
            return Color.danger
        } else if isWarning {
            return Color(hex: "#F39C12") // Warning orange
        } else {
            return Color.accent
        }
    }

    private var statusText: String {
        if isOverBudget {
            return "Over budget by $\(Int(abs(remaining)))"
        } else if isWarning {
            return "Approaching limit - $\(Int(remaining)) left"
        } else {
            return "$\(Int(remaining)) remaining this month"
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            // Header
            HStack {
                Image(systemName: "chart.bar.fill")
                    .foregroundStyle(progressColor)
                Text("Monthly Spending")
                    .font(.roundedCaption)
                    .foregroundStyle(Color.textSecondary)
                Spacer()
                Text("\(daysRemaining) days left")
                    .font(.roundedCaption)
                    .foregroundStyle(Color.textSecondary)
            }

            // Main amounts
            HStack(alignment: .firstTextBaseline) {
                Text("$\(Int(amountSpent))")
                    .font(.system(size: 36, weight: .bold, design: .rounded))
                    .monospacedDigit()
                    .foregroundStyle(progressColor)

                Text("of $\(Int(disposableIncome))")
                    .font(.roundedBody)
                    .foregroundStyle(Color.textSecondary)

                Spacer()
            }

            // Progress bar
            GeometryReader { geometry in
                ZStack(alignment: .leading) {
                    // Background track
                    RoundedRectangle(cornerRadius: 8)
                        .fill(Color.appBackground)
                        .frame(height: 16)

                    // Filled portion
                    if isOverBudget {
                        // Full bar + overflow indicator
                        HStack(spacing: 0) {
                            RoundedRectangle(cornerRadius: 8)
                                .fill(Color.danger)
                                .frame(width: geometry.size.width, height: 16)
                        }

                        // Overflow stripes pattern
                        RoundedRectangle(cornerRadius: 8)
                            .fill(
                                LinearGradient(
                                    colors: [Color.danger, Color.danger.opacity(0.7)],
                                    startPoint: .leading,
                                    endPoint: .trailing
                                )
                            )
                            .frame(height: 16)
                    } else {
                        RoundedRectangle(cornerRadius: 8)
                            .fill(progressColor)
                            .frame(width: geometry.size.width * min(percentSpent / 100, 1), height: 16)
                    }

                    // 75% warning marker
                    if !isOverBudget {
                        Rectangle()
                            .fill(Color.textSecondary.opacity(0.5))
                            .frame(width: 2, height: 20)
                            .offset(x: geometry.size.width * 0.75 - 1)
                    }
                }
            }
            .frame(height: 16)

            // Status text
            HStack {
                if isOverBudget {
                    Image(systemName: "exclamationmark.triangle.fill")
                        .foregroundStyle(Color.danger)
                        .font(.caption)
                } else if isWarning {
                    Image(systemName: "exclamationmark.circle.fill")
                        .foregroundStyle(Color(hex: "#F39C12"))
                        .font(.caption)
                }

                Text(statusText)
                    .font(.roundedCaption)
                    .foregroundStyle(isOverBudget ? Color.danger : (isWarning ? Color(hex: "#F39C12") : Color.textSecondary))

                Spacer()

                Text("\(Int(percentSpent))% spent")
                    .font(.roundedCaption)
                    .monospacedDigit()
                    .foregroundStyle(Color.textSecondary)
            }
        }
        .padding(20)
        .frame(maxWidth: .infinity)
        .background(Color.surface)
        .clipShape(RoundedRectangle(cornerRadius: 20))
    }
}

// MARK: - Spending Item for Chart

struct SpendingItem: Identifiable {
    let id: String
    let name: String
    let amount: Double
    let color: String
}

// MARK: - Category Colors

struct CategoryColors {
    // Predefined colors for common spending categories
    static let colors: [String: String] = [
        // Housing
        "rent": "#FF6B6B",
        "rent/mortgage": "#FF6B6B",
        "mortgage": "#FF6B6B",

        // Utilities & Bills
        "utilities": "#FF8E72",
        "subscriptions": "#FFA07A",

        // Food
        "groceries": "#4ECDC4",
        "dining": "#45B7D1",
        "dining & entertainment": "#45B7D1",
        "restaurants": "#5BC0DE",

        // Transportation
        "transportation": "#9B59B6",
        "gas": "#8E44AD",
        "car": "#7D3C98",
        "transit": "#A569BD",

        // Shopping
        "clothes": "#E91E63",
        "clothing": "#E91E63",
        "shopping": "#F06292",

        // Savings
        "savings": "#96CEB4",
        "emergency fund": "#88D8B0",
        "vacation fund": "#7FCDCD",
        "general savings": "#96CEB4",

        // Events
        "events": "#FFEAA7",
        "upcoming events": "#FFEAA7",

        // Entertainment
        "entertainment": "#F39C12",
        "hobbies": "#E67E22",

        // Health
        "health": "#1ABC9C",
        "healthcare": "#16A085",
        "gym": "#48C9B0",

        // Education
        "education": "#3498DB",

        // Personal
        "personal": "#D35400",
        "personal care": "#E74C3C"
    ]

    // Fallback colors for categories not in the predefined list
    static let fallbackColors = [
        "#6C5CE7", "#00B894", "#FDCB6E", "#E17055",
        "#74B9FF", "#A29BFE", "#55EFC4", "#FFEAA7"
    ]

    static func color(for category: String, fallbackIndex: Int = 0) -> String {
        let lowercased = category.lowercased()
        if let color = colors[lowercased] {
            return color
        }
        // Check for partial matches
        for (key, color) in colors {
            if lowercased.contains(key) || key.contains(lowercased) {
                return color
            }
        }
        return fallbackColors[fallbackIndex % fallbackColors.count]
    }
}

// MARK: - Budget Breakdown Card

struct BudgetBreakdownCard: View {
    let categories: [BudgetCategory]
    let totalIncome: Double

    // Flatten all items from categories into individual spending items
    private var spendingItems: [SpendingItem] {
        var items: [SpendingItem] = []
        var fallbackColorIndex = 0

        for category in categories {
            if let categoryItems = category.items, !categoryItems.isEmpty {
                // Add individual items from this category
                for item in categoryItems where item.amount > 0 {
                    let color = CategoryColors.color(for: item.name, fallbackIndex: fallbackColorIndex)
                    items.append(SpendingItem(
                        id: "\(category.id)-\(item.name)",
                        name: item.name,
                        amount: item.amount,
                        color: color
                    ))
                    fallbackColorIndex += 1
                }
            } else if category.amount > 0 {
                // No items, use the category itself
                let color = CategoryColors.color(for: category.name, fallbackIndex: fallbackColorIndex)
                items.append(SpendingItem(
                    id: category.id,
                    name: category.name,
                    amount: category.amount,
                    color: color
                ))
                fallbackColorIndex += 1
            }
        }

        // Sort by amount descending for better visualization
        return items.sorted { $0.amount > $1.amount }
    }

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

            // Donut chart with spending items
            SpendingDonutChartView(items: spendingItems)
                .frame(height: 120)

            // Category list
            VStack(spacing: 8) {
                ForEach(spendingItems) { item in
                    HStack {
                        Circle()
                            .fill(Color(hex: item.color))
                            .frame(width: 8, height: 8)

                        Text(item.name)
                            .font(.roundedCaption)
                            .foregroundStyle(Color.textPrimary)

                        Spacer()

                        Text("$\(item.amount, specifier: "%.0f")")
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

// MARK: - Spending Donut Chart View

struct SpendingDonutChartView: View {
    let items: [SpendingItem]

    private var total: Double {
        items.reduce(0) { $0 + $1.amount }
    }

    var body: some View {
        GeometryReader { geometry in
            let size = min(geometry.size.width, geometry.size.height)

            ZStack {
                ForEach(Array(items.enumerated()), id: \.element.id) { index, item in
                    let startAngle = startAngle(for: index)
                    let endAngle = endAngle(for: index)

                    Circle()
                        .trim(from: startAngle / 360, to: endAngle / 360)
                        .stroke(
                            Color(hex: item.color),
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
        let preceding = items.prefix(index).reduce(0) { $0 + $1.amount }
        return (preceding / total) * 360
    }

    private func endAngle(for index: Int) -> Double {
        guard total > 0 else { return 0 }
        let including = items.prefix(index + 1).reduce(0) { $0 + $1.amount }
        return (including / total) * 360
    }
}

// MARK: - Legacy Donut Chart View (kept for compatibility)

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
            BudgetCategory(id: "fixed", name: "Fixed Essentials", amount: 1450, color: "#FF6B6B", items: [
                BudgetItem(name: "Rent", amount: 1200),
                BudgetItem(name: "Utilities", amount: 150),
                BudgetItem(name: "Subscriptions", amount: 100)
            ]),
            BudgetCategory(id: "flexible", name: "Flexible Spending", amount: 600, color: "#4ECDC4", items: [
                BudgetItem(name: "Groceries", amount: 400),
                BudgetItem(name: "Transportation", amount: 200)
            ]),
            BudgetCategory(id: "discretionary", name: "Discretionary", amount: 300, color: "#45B7D1", items: [
                BudgetItem(name: "Dining & Entertainment", amount: 200),
                BudgetItem(name: "Clothes", amount: 100)
            ]),
            BudgetCategory(id: "savings", name: "Savings Goals", amount: 350, color: "#96CEB4", items: [
                BudgetItem(name: "Emergency Fund", amount: 200),
                BudgetItem(name: "Vacation Fund", amount: 150)
            ])
        ],
        totalIncome: 3500
    )
    .padding()
    .background(Color.appBackground)
}

#Preview("Spending Progress - Normal") {
    SpendingProgressCard(disposableIncome: 1200, amountSpent: 450, daysRemaining: 18)
        .padding()
        .background(Color.appBackground)
}

#Preview("Spending Progress - Warning") {
    SpendingProgressCard(disposableIncome: 1200, amountSpent: 950, daysRemaining: 8)
        .padding()
        .background(Color.appBackground)
}

#Preview("Spending Progress - Over Budget") {
    SpendingProgressCard(disposableIncome: 1200, amountSpent: 1450, daysRemaining: 3)
        .padding()
        .background(Color.appBackground)
}

#Preview("Generate Plan CTA") {
    GeneratePlanCard { }
        .padding()
        .background(Color.appBackground)
}
