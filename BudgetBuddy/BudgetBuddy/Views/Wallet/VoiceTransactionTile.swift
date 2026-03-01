//
//  VoiceTransactionTile.swift
//  BudgetBuddy
//
//  Tile on the Wallet home screen to start voice transaction recording
//

import SwiftUI

struct VoiceTransactionTile: View {
    let onTap: () -> Void

    var body: some View {
        Button(action: onTap) {
            HStack(spacing: 14) {
                ZStack {
                    Circle()
                        .fill(Color.accent.opacity(0.15))
                        .frame(width: 44, height: 44)
                    Image(systemName: "mic.fill")
                        .font(.system(size: 20))
                        .foregroundStyle(Color.accent)
                }

                VStack(alignment: .leading, spacing: 2) {
                    Text("Record a Transaction")
                        .font(.roundedHeadline)
                        .foregroundStyle(Color.textPrimary)
                    Text("Speak to log your spending")
                        .font(.roundedCaption)
                        .foregroundStyle(Color.textSecondary)
                }

                Spacer()

                Image(systemName: "chevron.right")
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundStyle(Color.textSecondary)
            }
            .walletCard()
        }
        .buttonStyle(.plain)
    }
}
