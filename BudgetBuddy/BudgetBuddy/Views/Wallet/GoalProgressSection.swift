//
//  GoalProgressSection.swift
//  BudgetBuddy
//
//  Shows all savings goals with progress bars
//

import SwiftUI

struct GoalProgressSection: View {
    let goals: [SavingsGoal]

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Label("Goals", systemImage: "target")
                .font(.roundedCaption)
                .foregroundStyle(Color.textSecondary)

            if goals.isEmpty {
                HStack {
                    Image(systemName: "target")
                        .foregroundStyle(Color.textSecondary)
                    Text("Create a plan to set goals")
                        .font(.roundedCaption)
                        .foregroundStyle(Color.textSecondary)
                }
                .padding(.vertical, 4)
            } else {
                ForEach(goals) { goal in
                    GoalRow(goal: goal)
                }
            }
        }
        .walletCard()
    }
}

// MARK: - Goal Row

private struct GoalRow: View {
    let goal: SavingsGoal

    private var progress: Double {
        guard goal.target > 0 else { return 0 }
        return min(1, goal.current / goal.target)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text(goal.name)
                    .font(.system(.subheadline, design: .rounded, weight: .medium))
                    .foregroundStyle(Color.textPrimary)

                Spacer()

                Text("\(Int(progress * 100))%")
                    .font(.system(.caption, design: .rounded, weight: .semibold))
                    .foregroundStyle(Color.accent)
            }

            ProgressBar(progress: progress)

            HStack {
                Text(goal.current.formatted(.currency(code: "USD")))
                    .font(.system(.caption2, design: .rounded))
                    .foregroundStyle(Color.textSecondary)

                Spacer()

                Text(goal.target.formatted(.currency(code: "USD")))
                    .font(.system(.caption2, design: .rounded))
                    .foregroundStyle(Color.textSecondary)
            }
        }
    }
}
