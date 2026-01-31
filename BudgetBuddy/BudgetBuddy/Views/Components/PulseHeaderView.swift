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

    init(safeToSpend: Double = 124.0, isHealthy: Bool = true, status: String = "On Track") {
        self.safeToSpend = safeToSpend
        self.isHealthy = isHealthy
        self.status = status
    }

    var body: some View {
        VStack(spacing: 8) {
            // Safe-to-Spend Amount
            HStack(spacing: 4) {
                Text("$")
                    .font(.rounded(.title2, weight: .medium))
                    .foregroundStyle(Color.textSecondary)

                Text("\(Int(safeToSpend))")
                    .font(.system(size: 48, weight: .bold, design: .rounded))
                    .monospacedDigit()
                    .foregroundStyle(Color.textPrimary)
            }
            .padding(.horizontal, 24)
            .padding(.vertical, 12)
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

            // Status Label
            HStack(spacing: 6) {
                Circle()
                    .fill(isHealthy ? Color.accent : Color.danger)
                    .frame(width: 8, height: 8)

                Text("Status: \(status)")
                    .font(.roundedCaption)
                    .foregroundStyle(Color.textSecondary)
            }

            // Safe-to-Spend Label
            Text("Safe to Spend Today")
                .font(.roundedCaption)
                .foregroundStyle(Color.textSecondary)
        }
        .padding(.vertical, 20)
        .frame(maxWidth: .infinity)
        .background(
            Color.background
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
    .background(Color.background)
}
