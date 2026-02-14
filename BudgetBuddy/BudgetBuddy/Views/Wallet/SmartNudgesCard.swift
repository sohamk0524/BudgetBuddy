//
//  SmartNudgesCard.swift
//  BudgetBuddy
//
//  Shows AI-generated spending nudges
//

import SwiftUI

struct SmartNudgesCard: View {
    let nudges: [SmartNudge]

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Label("Smart Insights", systemImage: "lightbulb.fill")
                .font(.roundedCaption)
                .foregroundStyle(Color.textSecondary)

            if nudges.isEmpty {
                HStack {
                    Image(systemName: "sparkles")
                        .foregroundStyle(Color.textSecondary)
                    Text("Insights will appear as we learn your spending patterns")
                        .font(.roundedCaption)
                        .foregroundStyle(Color.textSecondary)
                }
                .padding(.vertical, 4)
            } else {
                ForEach(nudges.prefix(3)) { nudge in
                    NudgeRow(nudge: nudge)
                }
            }
        }
        .walletCard()
    }
}

// MARK: - Nudge Row

private struct NudgeRow: View {
    let nudge: SmartNudge

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            Image(systemName: iconForType(nudge.type ?? ""))
                .foregroundStyle(colorForType(nudge.type ?? ""))
                .font(.system(size: 18))
                .frame(width: 24)

            VStack(alignment: .leading, spacing: 4) {
                Text(nudge.title ?? "Insight")
                    .font(.system(.subheadline, design: .rounded, weight: .semibold))
                    .foregroundStyle(Color.textPrimary)

                Text(nudge.message ?? "")
                    .font(.system(.caption, design: .rounded))
                    .foregroundStyle(Color.textSecondary)
                    .lineLimit(2)

                if let savings = nudge.potentialSavings, savings > 0 {
                    Text("Save \(savings.formatted(.currency(code: "USD")))")
                        .font(.system(.caption2, design: .rounded, weight: .semibold))
                        .foregroundStyle(Color.accent)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 2)
                        .background(Color.accent.opacity(0.15))
                        .clipShape(Capsule())
                }
            }
        }
    }

    private func iconForType(_ type: String) -> String {
        switch type {
        case "spending_reduction":
            return "arrow.down.circle.fill"
        case "positive_reinforcement":
            return "checkmark.circle.fill"
        case "goal_reminder":
            return "target"
        default:
            return "lightbulb.fill"
        }
    }

    private func colorForType(_ type: String) -> Color {
        switch type {
        case "spending_reduction":
            return Color.danger
        case "positive_reinforcement":
            return Color.accent
        case "goal_reminder":
            return Color.accent
        default:
            return Color.textSecondary
        }
    }
}
