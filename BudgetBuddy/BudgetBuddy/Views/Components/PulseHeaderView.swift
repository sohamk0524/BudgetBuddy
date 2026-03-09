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

    init(safeToSpend: Double = 124, isHealthy: Bool = true, status: String = "On Track") {
        self.safeToSpend = safeToSpend
        self.isHealthy = isHealthy
        self.status = status
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
        PulseHeaderView()

        PulseHeaderView(
            safeToSpend: 42.0,
            isHealthy: false,
            status: "Over Budget"
        )

        Spacer()
    }
    .background(Color.appBackground)
}
