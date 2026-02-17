//
//  PlanDashboardCards.swift
//  BudgetBuddy
//
//  Card components for the spending plan dashboard
//

import SwiftUI
import Charts

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

// MARK: - User Savings Goals Card

struct UserSavingsGoalsCard: View {
    let goals: [SavingsGoal]
    var onTapGoal: (SavingsGoal) -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                Image(systemName: "flag.fill")
                    .foregroundStyle(Color.accent)
                Text("My Savings Goals")
                    .font(.roundedCaption)
                    .foregroundStyle(Color.textSecondary)
                Spacer()
            }

            if goals.isEmpty {
                Text("No savings goals yet. Tap below to add one!")
                    .font(.roundedCaption)
                    .foregroundStyle(Color.textSecondary)
            } else {
                ForEach(goals) { goal in
                    let progress = goal.target > 0 ? goal.current / goal.target : 0

                    Button {
                        onTapGoal(goal)
                    } label: {
                        VStack(alignment: .leading, spacing: 8) {
                            HStack {
                                Text(goal.name)
                                    .font(.roundedBody)
                                    .foregroundStyle(Color.textPrimary)

                                Spacer()

                                Text("$\(goal.current, specifier: "%.0f") / $\(goal.target, specifier: "%.0f")")
                                    .font(.roundedCaption)
                                    .monospacedDigit()
                                    .foregroundStyle(Color.textSecondary)
                            }

                            GeometryReader { geometry in
                                ZStack(alignment: .leading) {
                                    RoundedRectangle(cornerRadius: 4)
                                        .fill(Color.appBackground)
                                        .frame(height: 8)

                                    RoundedRectangle(cornerRadius: 4)
                                        .fill(progress >= 1.0 ? Color(hex: "#96CEB4") : Color.accent)
                                        .frame(width: geometry.size.width * min(progress, 1.0), height: 8)
                                        .animation(.spring, value: progress)
                                }
                            }
                            .frame(height: 8)

                            HStack {
                                Spacer()
                                Text("\(Int(progress * 100))%")
                                    .font(.system(.caption2, design: .rounded))
                                    .monospacedDigit()
                                    .foregroundStyle(progress >= 1.0 ? Color(hex: "#96CEB4") : Color.accent)
                            }
                        }
                        .padding(12)
                        .background(Color.appBackground)
                        .clipShape(RoundedRectangle(cornerRadius: 12))
                    }
                    .buttonStyle(.plain)
                }
            }
        }
        .padding(20)
        .frame(maxWidth: .infinity)
        .background(Color.surface)
        .clipShape(RoundedRectangle(cornerRadius: 20))
    }
}

// MARK: - Add Savings Goal Sheet

struct AddSavingsGoalSheet: View {
    @State private var goalName: String = ""
    @State private var targetAmount: String = ""
    var onAdd: (String, Double) -> Void
    @Environment(\.dismiss) private var dismiss

    private var isValid: Bool {
        !goalName.trimmingCharacters(in: .whitespaces).isEmpty && (Double(targetAmount) ?? 0) > 0
    }

    var body: some View {
        NavigationStack {
            VStack(spacing: 24) {
                VStack(alignment: .leading, spacing: 8) {
                    Text("Goal Name")
                        .font(.roundedCaption)
                        .foregroundStyle(Color.textSecondary)

                    TextField("e.g. Emergency Fund", text: $goalName)
                        .font(.roundedBody)
                        .padding()
                        .background(Color.surface)
                        .clipShape(RoundedRectangle(cornerRadius: 12))
                }

                VStack(alignment: .leading, spacing: 8) {
                    Text("Target Amount")
                        .font(.roundedCaption)
                        .foregroundStyle(Color.textSecondary)

                    HStack {
                        Text("$")
                            .font(.roundedBody)
                            .foregroundStyle(Color.textSecondary)
                        TextField("0", text: $targetAmount)
                            .font(.roundedBody)
                            .keyboardType(.decimalPad)
                    }
                    .padding()
                    .background(Color.surface)
                    .clipShape(RoundedRectangle(cornerRadius: 12))
                }

                Button {
                    if let target = Double(targetAmount), isValid {
                        onAdd(goalName.trimmingCharacters(in: .whitespaces), target)
                        dismiss()
                    }
                } label: {
                    Text("Add Goal")
                        .font(.roundedHeadline)
                        .foregroundStyle(Color.appBackground)
                        .frame(maxWidth: .infinity)
                        .padding()
                }
                .background(isValid ? Color.accent : Color.accent.opacity(0.4))
                .clipShape(RoundedRectangle(cornerRadius: 12))
                .disabled(!isValid)

                Spacer()
            }
            .padding(24)
            .background(Color.appBackground)
            .navigationTitle("New Savings Goal")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                        .foregroundStyle(Color.textSecondary)
                }
            }
        }
        .presentationDetents([.medium])
    }
}

// MARK: - Update Saved Amount Sheet

struct UpdateSavedAmountSheet: View {
    let goal: SavingsGoal
    @State private var additionalAmount: String = ""
    var onSave: (UUID, Double) -> Void
    var onDelete: (UUID) -> Void
    @Environment(\.dismiss) private var dismiss

    private var progress: Double {
        goal.target > 0 ? goal.current / goal.target : 0
    }

    var body: some View {
        NavigationStack {
            VStack(spacing: 24) {
                // Goal summary
                VStack(spacing: 12) {
                    Text(goal.name)
                        .font(.roundedTitle)
                        .foregroundStyle(Color.textPrimary)

                    Text("$\(goal.current, specifier: "%.0f") of $\(goal.target, specifier: "%.0f")")
                        .font(.roundedBody)
                        .monospacedDigit()
                        .foregroundStyle(Color.textSecondary)

                    GeometryReader { geometry in
                        ZStack(alignment: .leading) {
                            RoundedRectangle(cornerRadius: 6)
                                .fill(Color.surface)
                                .frame(height: 12)

                            RoundedRectangle(cornerRadius: 6)
                                .fill(progress >= 1.0 ? Color(hex: "#96CEB4") : Color.accent)
                                .frame(width: geometry.size.width * min(progress, 1.0), height: 12)
                                .animation(.spring, value: progress)
                        }
                    }
                    .frame(height: 12)

                    Text("\(Int(progress * 100))% complete")
                        .font(.roundedCaption)
                        .foregroundStyle(progress >= 1.0 ? Color(hex: "#96CEB4") : Color.accent)
                }
                .padding()
                .frame(maxWidth: .infinity)
                .background(Color.surface)
                .clipShape(RoundedRectangle(cornerRadius: 16))

                // Add amount field
                VStack(alignment: .leading, spacing: 8) {
                    Text("Add to Savings")
                        .font(.roundedCaption)
                        .foregroundStyle(Color.textSecondary)

                    HStack {
                        Text("$")
                            .font(.roundedBody)
                            .foregroundStyle(Color.textSecondary)
                        TextField("0", text: $additionalAmount)
                            .font(.roundedBody)
                            .keyboardType(.decimalPad)
                    }
                    .padding()
                    .background(Color.surface)
                    .clipShape(RoundedRectangle(cornerRadius: 12))
                }

                Button {
                    if let amount = Double(additionalAmount), amount > 0 {
                        onSave(goal.id, amount)
                        dismiss()
                    }
                } label: {
                    Text("Save Progress")
                        .font(.roundedHeadline)
                        .foregroundStyle(Color.appBackground)
                        .frame(maxWidth: .infinity)
                        .padding()
                }
                .background((Double(additionalAmount) ?? 0) > 0 ? Color.accent : Color.accent.opacity(0.4))
                .clipShape(RoundedRectangle(cornerRadius: 12))
                .disabled((Double(additionalAmount) ?? 0) <= 0)

                Spacer()

                // Delete button
                Button {
                    onDelete(goal.id)
                    dismiss()
                } label: {
                    Text("Delete Goal")
                        .font(.roundedCaption)
                        .foregroundStyle(Color.danger)
                }
            }
            .padding(24)
            .background(Color.appBackground)
            .navigationTitle("Update Goal")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Done") { dismiss() }
                        .foregroundStyle(Color.textSecondary)
                }
            }
        }
        .presentationDetents([.medium])
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

// MARK: - Chart Data Helpers

struct PlanChartDataPoint: Identifiable {
    let id = UUID()
    let label: String
    let value: Double
}

struct GroupedChartDataPoint: Identifiable {
    let id = UUID()
    let category: String
    let group: String
    let value: Double
}

// MARK: - Weekly Spending Heatmap

struct WeeklySpendingHeatmap: View {
    let data: [(day: String, amount: Double)]

    private var maxAmount: Double {
        data.map(\.amount).max() ?? 1
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                Image(systemName: "calendar")
                    .foregroundStyle(Color.accent)
                Text("Weekly Spending")
                    .font(.roundedCaption)
                    .foregroundStyle(Color.textSecondary)
                Spacer()
            }

            HStack(spacing: 8) {
                ForEach(data.indices, id: \.self) { index in
                    let item = data[index]
                    let intensity = item.amount / maxAmount

                    VStack(spacing: 6) {
                        RoundedRectangle(cornerRadius: 8)
                            .fill(Color.accent.opacity(max(0.15, intensity)))
                            .frame(height: 56)
                            .overlay(
                                Text("$\(Int(item.amount))")
                                    .font(.system(.caption2, design: .rounded, weight: .medium))
                                    .monospacedDigit()
                                    .foregroundStyle(intensity > 0.5 ? Color.appBackground : Color.textPrimary)
                            )

                        Text(item.day)
                            .font(.system(.caption2, design: .rounded))
                            .foregroundStyle(Color.textSecondary)
                    }
                    .frame(maxWidth: .infinity)
                }
            }
        }
        .padding(20)
        .frame(maxWidth: .infinity)
        .background(Color.surface)
        .clipShape(RoundedRectangle(cornerRadius: 20))
    }
}

// MARK: - Income/Expense Waterfall

struct IncomeExpenseWaterfall: View {
    let totalIncome: Double
    let categories: [BudgetCategory]

    private struct WaterfallItem: Identifiable {
        let id = UUID()
        let label: String
        let amount: Double
        let runningTotal: Double
        let isIncome: Bool
        let isRemaining: Bool
    }

    private var items: [WaterfallItem] {
        var result: [WaterfallItem] = []
        var running = totalIncome

        result.append(WaterfallItem(
            label: "Income",
            amount: totalIncome,
            runningTotal: running,
            isIncome: true,
            isRemaining: false
        ))

        for category in categories {
            guard category.amount > 0 else { continue }
            running -= category.amount
            result.append(WaterfallItem(
                label: category.name,
                amount: category.amount,
                runningTotal: running,
                isIncome: false,
                isRemaining: false
            ))
        }

        result.append(WaterfallItem(
            label: "Remaining",
            amount: max(running, 0),
            runningTotal: max(running, 0),
            isIncome: false,
            isRemaining: true
        ))

        return result
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                Image(systemName: "arrow.down.right.and.arrow.up.left")
                    .foregroundStyle(Color.accent)
                Text("Income & Expenses")
                    .font(.roundedCaption)
                    .foregroundStyle(Color.textSecondary)
                Spacer()
            }

            VStack(spacing: 4) {
                ForEach(items) { item in
                    HStack(spacing: 12) {
                        Text(item.label)
                            .font(.roundedCaption)
                            .foregroundStyle(Color.textPrimary)
                            .frame(width: 90, alignment: .leading)
                            .lineLimit(1)

                        GeometryReader { geo in
                            let maxWidth = geo.size.width
                            let barWidth = totalIncome > 0
                                ? maxWidth * (item.isRemaining ? item.amount : (item.isIncome ? item.amount : item.amount)) / totalIncome
                                : 0

                            HStack(spacing: 0) {
                                if !item.isIncome && !item.isRemaining {
                                    Spacer()
                                        .frame(width: max(0, maxWidth * item.runningTotal / totalIncome))
                                }

                                RoundedRectangle(cornerRadius: 4)
                                    .fill(
                                        item.isIncome ? Color.accent :
                                        item.isRemaining ? Color.accent.opacity(0.7) :
                                        Color(hex: "#F43F5E").opacity(0.7)
                                    )
                                    .frame(width: max(4, barWidth), height: 20)

                                Spacer(minLength: 0)
                            }
                        }
                        .frame(height: 20)

                        Text("$\(Int(item.isIncome || item.isRemaining ? item.amount : item.amount))")
                            .font(.system(.caption2, design: .rounded, weight: .medium))
                            .monospacedDigit()
                            .foregroundStyle(
                                item.isIncome ? Color.accent :
                                item.isRemaining ? Color.accent :
                                Color.textSecondary
                            )
                            .frame(width: 56, alignment: .trailing)
                    }
                    .frame(height: 28)
                }
            }
        }
        .padding(20)
        .frame(maxWidth: .infinity)
        .background(Color.surface)
        .clipShape(RoundedRectangle(cornerRadius: 20))
    }
}

// MARK: - Month Spending Delta View

struct MonthSpendingDeltaView: View {
    let thisMonthData: [(category: String, amount: Double)]
    let lastMonthData: [(category: String, amount: Double)]

    @State private var expandedCategory: String?
    @State private var animateBars = false

    // MARK: - Computed Data

    private struct DeltaRow: Identifiable {
        let id: String
        let category: String
        let thisMonth: Double
        let lastMonth: Double
        var delta: Double { thisMonth - lastMonth }
        var absDelta: Double { abs(delta) }
        var percentChange: Double {
            guard lastMonth > 0 else { return thisMonth > 0 ? 100 : 0 }
            return (delta / lastMonth) * 100
        }
    }

    private var rows: [DeltaRow] {
        var allCategories: [String] = []
        for item in thisMonthData {
            if !allCategories.contains(where: { $0.lowercased() == item.category.lowercased() }) {
                allCategories.append(item.category)
            }
        }
        for item in lastMonthData {
            if !allCategories.contains(where: { $0.lowercased() == item.category.lowercased() }) {
                allCategories.append(item.category)
            }
        }

        return allCategories.map { cat in
            let thisAmount = thisMonthData.first(where: { $0.category.lowercased() == cat.lowercased() })?.amount ?? 0
            let lastAmount = lastMonthData.first(where: { $0.category.lowercased() == cat.lowercased() })?.amount ?? 0
            return DeltaRow(id: cat, category: cat, thisMonth: thisAmount, lastMonth: lastAmount)
        }
        .sorted { $0.absDelta > $1.absDelta }
    }

    private var maxAbsDelta: Double {
        rows.map(\.absDelta).max() ?? 1
    }

    private var thisMonthTotal: Double {
        thisMonthData.reduce(0) { $0 + $1.amount }
    }

    private var lastMonthTotal: Double {
        lastMonthData.reduce(0) { $0 + $1.amount }
    }

    private var totalDelta: Double {
        thisMonthTotal - lastMonthTotal
    }

    private var totalPercentChange: Double {
        guard lastMonthTotal > 0 else { return 0 }
        return (totalDelta / lastMonthTotal) * 100
    }

    // MARK: - Colors

    private func deltaColor(_ delta: Double) -> Color {
        if delta > 0 { return Color(hex: "#F43F5E") }      // Red — spending up
        if delta < 0 { return Color(hex: "#2DD4BF") }      // Green — spending down
        return Color.textSecondary                           // Neutral
    }

    // MARK: - Body

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            // Header
            HStack {
                Image(systemName: "arrow.up.arrow.down")
                    .foregroundStyle(Color.accent)
                Text("Monthly Change")
                    .font(.roundedCaption)
                    .foregroundStyle(Color.textSecondary)
                Spacer()
            }

            // Summary card
            summarySection

            // Separator
            Rectangle()
                .fill(Color.appBackground)
                .frame(height: 1)

            // Delta rows
            VStack(spacing: 2) {
                ForEach(rows) { row in
                    deltaRow(row)
                }
            }
        }
        .padding(20)
        .frame(maxWidth: .infinity)
        .background(Color.surface)
        .clipShape(RoundedRectangle(cornerRadius: 20))
        .onAppear {
            withAnimation(.easeOut(duration: 0.6).delay(0.15)) {
                animateBars = true
            }
        }
    }

    // MARK: - Summary

    private var summarySection: some View {
        HStack(spacing: 0) {
            // This month
            VStack(alignment: .leading, spacing: 4) {
                Text("This Month")
                    .font(.system(.caption2, design: .rounded))
                    .foregroundStyle(Color.textSecondary)
                Text("$\(Int(thisMonthTotal))")
                    .font(.system(.subheadline, design: .rounded, weight: .semibold))
                    .monospacedDigit()
                    .foregroundStyle(Color.textPrimary)
            }

            Spacer()

            // Last month
            VStack(alignment: .center, spacing: 4) {
                Text("Last Month")
                    .font(.system(.caption2, design: .rounded))
                    .foregroundStyle(Color.textSecondary)
                Text("$\(Int(lastMonthTotal))")
                    .font(.system(.subheadline, design: .rounded, weight: .semibold))
                    .monospacedDigit()
                    .foregroundStyle(Color.textPrimary)
            }

            Spacer()

            // Delta
            VStack(alignment: .trailing, spacing: 4) {
                Text("Change")
                    .font(.system(.caption2, design: .rounded))
                    .foregroundStyle(Color.textSecondary)
                HStack(spacing: 4) {
                    Text("\(totalDelta >= 0 ? "+" : "")$\(Int(totalDelta))")
                        .font(.system(.subheadline, design: .rounded, weight: .bold))
                        .monospacedDigit()
                        .foregroundStyle(deltaColor(totalDelta))

                    Text("(\(totalDelta >= 0 ? "+" : "")\(Int(totalPercentChange))%)")
                        .font(.system(.caption2, design: .rounded))
                        .foregroundStyle(deltaColor(totalDelta))
                }
            }
        }
    }

    // MARK: - Delta Row

    private func deltaRow(_ row: DeltaRow) -> some View {
        VStack(spacing: 0) {
            Button {
                withAnimation(.easeInOut(duration: 0.2)) {
                    expandedCategory = expandedCategory == row.category ? nil : row.category
                }
            } label: {
                HStack(spacing: 10) {
                    // Category name
                    Text(row.category)
                        .font(.system(.subheadline, design: .rounded))
                        .foregroundStyle(Color.textPrimary)
                        .lineLimit(1)
                        .frame(maxWidth: .infinity, alignment: .leading)

                    // Delta amount + arrow
                    HStack(spacing: 3) {
                        if row.delta != 0 {
                            Image(systemName: row.delta > 0 ? "arrow.up" : "arrow.down")
                                .font(.system(size: 9, weight: .bold))
                                .foregroundStyle(deltaColor(row.delta))
                        }

                        Text("\(row.delta >= 0 ? "+" : "-")$\(Int(row.absDelta))")
                            .font(.system(.caption, design: .rounded, weight: .semibold))
                            .monospacedDigit()
                            .foregroundStyle(deltaColor(row.delta))
                    }
                    .frame(width: 80, alignment: .trailing)

                    // Mini bar
                    GeometryReader { geo in
                        let fraction = maxAbsDelta > 0 ? row.absDelta / maxAbsDelta : 0
                        let barWidth = geo.size.width * fraction

                        HStack {
                            Spacer(minLength: 0)
                            RoundedRectangle(cornerRadius: 3)
                                .fill(deltaColor(row.delta).opacity(0.8))
                                .frame(width: animateBars ? max(row.absDelta > 0 ? 3 : 0, barWidth) : 0, height: 8)
                        }
                    }
                    .frame(width: 60, height: 8)
                }
                .padding(.vertical, 10)
            }
            .buttonStyle(.plain)

            // Expanded detail
            if expandedCategory == row.category {
                HStack {
                    VStack(alignment: .leading, spacing: 2) {
                        Text("This month")
                            .font(.system(.caption2, design: .rounded))
                            .foregroundStyle(Color.textSecondary)
                        Text("$\(Int(row.thisMonth))")
                            .font(.system(.caption, design: .rounded, weight: .medium))
                            .monospacedDigit()
                            .foregroundStyle(Color.textPrimary)
                    }

                    Spacer()

                    VStack(alignment: .center, spacing: 2) {
                        Text("Last month")
                            .font(.system(.caption2, design: .rounded))
                            .foregroundStyle(Color.textSecondary)
                        Text("$\(Int(row.lastMonth))")
                            .font(.system(.caption, design: .rounded, weight: .medium))
                            .monospacedDigit()
                            .foregroundStyle(Color.textPrimary)
                    }

                    Spacer()

                    VStack(alignment: .trailing, spacing: 2) {
                        Text("Change")
                            .font(.system(.caption2, design: .rounded))
                            .foregroundStyle(Color.textSecondary)
                        Text("\(row.percentChange >= 0 ? "+" : "")\(Int(row.percentChange))%")
                            .font(.system(.caption, design: .rounded, weight: .medium))
                            .monospacedDigit()
                            .foregroundStyle(deltaColor(row.delta))
                    }
                }
                .padding(.horizontal, 4)
                .padding(.bottom, 10)
                .transition(.opacity.combined(with: .move(edge: .top)))
            }

            // Subtle separator
            if row.id != rows.last?.id {
                Rectangle()
                    .fill(Color.appBackground.opacity(0.6))
                    .frame(height: 0.5)
            }
        }
    }
}

// MARK: - Semester Overview Chart

struct SemesterOverviewChart: View {
    let data: [(month: String, amount: Double)]

    private var chartPoints: [PlanChartDataPoint] {
        data.map { PlanChartDataPoint(label: $0.month, value: $0.amount) }
    }

    private var currentMonthLabel: String {
        let formatter = DateFormatter()
        formatter.dateFormat = "MMM"
        return formatter.string(from: Date())
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                Image(systemName: "chart.bar.xaxis")
                    .foregroundStyle(Color.accent)
                Text("Semester Overview")
                    .font(.roundedCaption)
                    .foregroundStyle(Color.textSecondary)
                Spacer()
            }

            Chart(chartPoints) { point in
                BarMark(
                    x: .value("Month", point.label),
                    y: .value("Amount", point.value)
                )
                .foregroundStyle(
                    point.label == currentMonthLabel ? Color.accent : Color.accent.opacity(0.4)
                )
                .cornerRadius(6)
            }
            .chartYAxis {
                AxisMarks(position: .leading) { value in
                    AxisValueLabel {
                        if let v = value.as(Double.self) {
                            Text("$\(Int(v))")
                                .font(.system(.caption2, design: .rounded))
                                .foregroundStyle(Color.textSecondary)
                        }
                    }
                    AxisGridLine(stroke: StrokeStyle(lineWidth: 0.5))
                        .foregroundStyle(Color.textSecondary.opacity(0.2))
                }
            }
            .chartXAxis {
                AxisMarks { value in
                    AxisValueLabel {
                        if let v = value.as(String.self) {
                            Text(v)
                                .font(.system(.caption2, design: .rounded))
                                .foregroundStyle(Color.textSecondary)
                        }
                    }
                }
            }
            .frame(height: 180)
        }
        .padding(20)
        .frame(maxWidth: .infinity)
        .background(Color.surface)
        .clipShape(RoundedRectangle(cornerRadius: 20))
    }
}

// MARK: - Semester Cost Breakdown

struct SemesterCostBreakdownCard: View {
    let data: [(category: String, amount: Double)]

    private var sorted: [(category: String, amount: Double)] {
        data.sorted { $0.amount > $1.amount }
    }

    private var maxAmount: Double {
        sorted.first?.amount ?? 1
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                Image(systemName: "graduationcap.fill")
                    .foregroundStyle(Color.accent)
                Text("Semester Costs")
                    .font(.roundedCaption)
                    .foregroundStyle(Color.textSecondary)
                Spacer()
            }

            VStack(spacing: 10) {
                ForEach(sorted.indices, id: \.self) { index in
                    let item = sorted[index]
                    let barFraction = item.amount / maxAmount

                    VStack(alignment: .leading, spacing: 4) {
                        HStack {
                            Text(item.category)
                                .font(.roundedCaption)
                                .foregroundStyle(Color.textPrimary)
                            Spacer()
                            Text("$\(Int(item.amount))")
                                .font(.system(.caption, design: .rounded, weight: .medium))
                                .monospacedDigit()
                                .foregroundStyle(Color.textSecondary)
                        }

                        GeometryReader { geo in
                            RoundedRectangle(cornerRadius: 4)
                                .fill(Color(hex: CategoryColors.color(for: item.category, fallbackIndex: index)))
                                .frame(width: geo.size.width * barFraction, height: 12)
                        }
                        .frame(height: 12)
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

// MARK: - Actual vs Planned Chart

struct ActualVsPlannedChart: View {
    let plannedCategories: [BudgetCategory]
    let actualSpending: [SpendingCategory]

    private var chartData: [GroupedChartDataPoint] {
        var points: [GroupedChartDataPoint] = []

        // Gather all unique category names
        var allNames: [String] = []

        // Flatten planned categories into individual items
        var plannedMap: [String: Double] = [:]
        for category in plannedCategories {
            if let items = category.items, !items.isEmpty {
                for item in items where item.amount > 0 {
                    let name = item.name
                    plannedMap[name.lowercased()] = (plannedMap[name.lowercased()] ?? 0) + item.amount
                    if !allNames.contains(where: { $0.lowercased() == name.lowercased() }) {
                        allNames.append(name)
                    }
                }
            } else if category.amount > 0 {
                plannedMap[category.name.lowercased()] = category.amount
                if !allNames.contains(where: { $0.lowercased() == category.name.lowercased() }) {
                    allNames.append(category.name)
                }
            }
        }

        // Add actual categories
        var actualMap: [String: Double] = [:]
        for item in actualSpending {
            actualMap[item.category.lowercased()] = item.amount
            if !allNames.contains(where: { $0.lowercased() == item.category.lowercased() }) {
                allNames.append(item.category)
            }
        }

        for name in allNames {
            let planned = plannedMap[name.lowercased()] ?? 0
            let actual = actualMap[name.lowercased()] ?? 0

            // Shorten names for chart readability
            let shortName = name.count > 12 ? String(name.prefix(10)) + ".." : name
            points.append(GroupedChartDataPoint(category: shortName, group: "Planned", value: planned))
            points.append(GroupedChartDataPoint(category: shortName, group: "Actual", value: actual))
        }

        return points
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                Image(systemName: "chart.bar.doc.horizontal.fill")
                    .foregroundStyle(Color.accent)
                Text("Actual vs Planned")
                    .font(.roundedCaption)
                    .foregroundStyle(Color.textSecondary)
                Spacer()
            }

            if chartData.isEmpty {
                Text("No data available yet")
                    .font(.roundedCaption)
                    .foregroundStyle(Color.textSecondary)
                    .frame(maxWidth: .infinity, minHeight: 100)
            } else {
                Chart(chartData) { point in
                    BarMark(
                        x: .value("Category", point.category),
                        y: .value("Amount", point.value)
                    )
                    .foregroundStyle(by: .value("Type", point.group))
                    .position(by: .value("Type", point.group))
                }
                .chartForegroundStyleScale([
                    "Planned": Color.accent,
                    "Actual": Color(hex: "#F39C12")
                ])
                .chartLegend(position: .bottom, spacing: 8)
                .chartYAxis {
                    AxisMarks(position: .leading) { value in
                        AxisValueLabel {
                            if let v = value.as(Double.self) {
                                Text("$\(Int(v))")
                                    .font(.system(.caption2, design: .rounded))
                                    .foregroundStyle(Color.textSecondary)
                            }
                        }
                        AxisGridLine(stroke: StrokeStyle(lineWidth: 0.5))
                            .foregroundStyle(Color.textSecondary.opacity(0.2))
                    }
                }
                .chartXAxis {
                    AxisMarks { value in
                        AxisValueLabel {
                            if let v = value.as(String.self) {
                                Text(v)
                                    .font(.system(.caption2, design: .rounded))
                                    .foregroundStyle(Color.textSecondary)
                                    .lineLimit(1)
                            }
                        }
                    }
                }
                .frame(height: 220)
            }
        }
        .padding(20)
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
