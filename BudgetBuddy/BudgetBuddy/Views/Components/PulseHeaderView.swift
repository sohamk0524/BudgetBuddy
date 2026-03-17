//
//  PulseHeaderView.swift
//  BudgetBuddy
//
//  The "Pulse Header" - A sticky header showing safe-to-spend amount
//

import SwiftUI

struct PulseHeaderView: View {
    let safeToSpend: Double
    let isHealthy: Bool
    let status: String
    var savingsStreak: Int = 0

    init(safeToSpend: Double = 124, isHealthy: Bool = true, status: String = "On Track", savingsStreak: Int = 0) {
        self.safeToSpend = safeToSpend
        self.isHealthy = isHealthy
        self.status = status
        self.savingsStreak = savingsStreak
    }

    var body: some View {
        HStack(spacing: 10) {
            // Labels
            VStack(alignment: .leading, spacing: 2) {
                Text("Safe to Spend Today")
                    .font(.system(.subheadline, design: .rounded, weight: .medium))
                    .foregroundStyle(Color.textPrimary)

                HStack(spacing: 5) {
                    Circle()
                        .fill(isHealthy ? Color.accent : Color.danger)
                        .frame(width: 6, height: 6)

                    Text(status)
                        .font(.roundedCaption)
                        .foregroundStyle(Color.textSecondary)
                }
            }

            Spacer()

            // Savings Streak
            if savingsStreak >= 1 {
                HStack(spacing: 4) {
                    Image(systemName: "flame.fill")
                        .font(.system(size: 18))
                        .foregroundStyle(.orange)

                    Text("\(savingsStreak)w")
                        .font(.system(size: 22, weight: .bold, design: .rounded))
                        .monospacedDigit()
                        .foregroundStyle(.orange)
                }
                .padding(.horizontal, 12)
                .padding(.vertical, 6)
                .background(
                    Capsule()
                        .fill(Color.orange.opacity(0.15))
                )
            }

            // Safe-to-Spend Amount
            HStack(spacing: 3) {
                Text("$")
                    .font(.rounded(.body, weight: .medium))
                    .foregroundStyle(Color.textSecondary)

                Text("\(Int(safeToSpend))")
                    .font(.system(size: 28, weight: .bold, design: .rounded))
                    .monospacedDigit()
                    .foregroundStyle(Color.textPrimary)
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 8)
            .background(
                Capsule()
                    .fill(isHealthy ? Color.accent.opacity(0.2) : Color.danger.opacity(0.2))
            )
            .overlay(
                Capsule()
                    .strokeBorder(
                        isHealthy ? Color.accent.opacity(0.5) : Color.danger.opacity(0.5),
                        lineWidth: 1
                    )
            )
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 12)
        .frame(maxWidth: .infinity)
        .background(
            Color.appBackground
                .shadow(color: .black.opacity(0.3), radius: 10, x: 0, y: 5)
        )
    }
}

// MARK: - Preview

#Preview {
    VStack(spacing: 0) {
        PulseHeaderView(savingsStreak: 3)

        PulseHeaderView(
            safeToSpend: 42.0,
            isHealthy: false,
            status: "Over Budget"
        )

        PulseHeaderView(
            safeToSpend: 200,
            savingsStreak: 12
        )

        Spacer()
    }
    .background(Color.appBackground)
}
