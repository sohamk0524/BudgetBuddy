//
//  TopExpensesCard.swift
//  BudgetBuddy
//
//  Shows top spending categories with proportional bars
//

import SwiftUI

struct TopExpensesCard: View {
    let topExpenses: [TopExpense]
    let source: String
    let onCustomize: () -> Void

    private var maxAmount: Double {
        topExpenses.first?.amount ?? 1
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            // Header
            HStack {
                Label("Top Expenses", systemImage: "chart.bar.fill")
                    .font(.roundedCaption)
                    .foregroundStyle(Color.textSecondary)

                Spacer()

                if source != "none" {
                    Text("via \(source == "plaid" ? "Plaid" : "Statement")")
                        .font(.system(.caption2, design: .rounded))
                        .foregroundStyle(Color.accent)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 2)
                        .background(Color.accent.opacity(0.15))
                        .clipShape(Capsule())
                }

                Button("Customize", action: onCustomize)
                    .font(.system(.caption2, design: .rounded, weight: .medium))
                    .foregroundStyle(Color.accent)
            }

            if topExpenses.isEmpty {
                VStack(spacing: 8) {
                    Image(systemName: "chart.bar.xaxis")
                        .font(.system(size: 24))
                        .foregroundStyle(Color.textSecondary)

                    Text("Link your bank to see spending insights")
                        .font(.roundedCaption)
                        .foregroundStyle(Color.textSecondary)
                        .multilineTextAlignment(.center)
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, 8)
            } else {
                ForEach(topExpenses.prefix(3)) { expense in
                    TopExpenseRow(expense: expense, maxAmount: maxAmount)
                }
            }
        }
        .walletCard()
    }
}

// MARK: - Expense Row

private struct TopExpenseRow: View {
    let expense: TopExpense
    let maxAmount: Double

    private var proportion: Double {
        guard maxAmount > 0 else { return 0 }
        return expense.amount / maxAmount
    }

    var body: some View {
        VStack(spacing: 6) {
            HStack {
                Image(systemName: iconForCategory(expense.category))
                    .foregroundStyle(Color.accent)
                    .frame(width: 20)

                Text(expense.category)
                    .font(.system(.subheadline, design: .rounded, weight: .medium))
                    .foregroundStyle(Color.textPrimary)

                Spacer()

                Text(expense.amount.formatted(.currency(code: "USD")))
                    .font(.system(.subheadline, design: .rounded, weight: .semibold))
                    .foregroundStyle(Color.textPrimary)
            }

            GeometryReader { geo in
                ZStack(alignment: .leading) {
                    RoundedRectangle(cornerRadius: 2)
                        .fill(Color.appBackground)
                    RoundedRectangle(cornerRadius: 2)
                        .fill(Color.accent.opacity(0.6))
                        .frame(width: geo.size.width * proportion)
                }
            }
            .frame(height: 4)
        }
    }

    private func iconForCategory(_ category: String) -> String {
        let lower = category.lowercased()
        if lower.contains("food") || lower.contains("dining") || lower.contains("restaurant") {
            return "fork.knife"
        } else if lower.contains("transport") || lower.contains("travel") {
            return "car.fill"
        } else if lower.contains("shop") || lower.contains("retail") {
            return "bag.fill"
        } else if lower.contains("entertainment") || lower.contains("recreation") {
            return "gamecontroller.fill"
        } else if lower.contains("rent") || lower.contains("housing") || lower.contains("mortgage") {
            return "house.fill"
        } else if lower.contains("health") || lower.contains("medical") {
            return "heart.fill"
        } else if lower.contains("transfer") || lower.contains("payment") {
            return "arrow.left.arrow.right"
        } else {
            return "creditcard.fill"
        }
    }
}

// MARK: - Category Editor Sheet

struct CategoryEditorSheet: View {
    let availableCategories: [String]
    @Binding var selectedCategories: [String]
    let onSave: ([String]) -> Void
    @Environment(\.dismiss) private var dismiss

    @State private var localSelection: Set<String> = []

    var body: some View {
        NavigationStack {
            List {
                ForEach(availableCategories, id: \.self) { category in
                    HStack {
                        Text(category)
                            .font(.roundedBody)
                            .foregroundStyle(Color.textPrimary)

                        Spacer()

                        Image(systemName: localSelection.contains(category) ? "checkmark.circle.fill" : "circle")
                            .foregroundStyle(localSelection.contains(category) ? Color.accent : Color.textSecondary)
                    }
                    .contentShape(Rectangle())
                    .onTapGesture {
                        if localSelection.contains(category) {
                            localSelection.remove(category)
                        } else {
                            localSelection.insert(category)
                        }
                    }
                    .listRowBackground(Color.surface)
                }
            }
            .scrollContentBackground(.hidden)
            .background(Color.appBackground)
            .navigationTitle("Customize Categories")
            .navigationBarTitleDisplayMode(.inline)
            .toolbarBackground(Color.surface, for: .navigationBar)
            .toolbarColorScheme(.dark, for: .navigationBar)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                        .foregroundStyle(Color.textSecondary)
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save") {
                        onSave(Array(localSelection))
                        dismiss()
                    }
                    .foregroundStyle(Color.accent)
                }
            }
        }
        .onAppear {
            localSelection = Set(selectedCategories)
        }
    }
}
