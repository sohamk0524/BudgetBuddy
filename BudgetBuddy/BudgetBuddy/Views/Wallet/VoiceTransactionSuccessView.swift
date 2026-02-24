//
//  VoiceTransactionSuccessView.swift
//  BudgetBuddy
//
//  Success feedback screen after a voice transaction is saved
//

import SwiftUI

struct VoiceTransactionSuccessView: View {
    let onDismiss: () -> Void

    @State private var showCheckmark = false

    var body: some View {
        VStack(spacing: 24) {
            Spacer()

            ZStack {
                Circle()
                    .fill(Color.accent.opacity(0.15))
                    .frame(width: 120, height: 120)

                Image(systemName: "checkmark.circle.fill")
                    .font(.system(size: 64))
                    .foregroundStyle(Color.accent)
                    .scaleEffect(showCheckmark ? 1.0 : 0.5)
                    .opacity(showCheckmark ? 1.0 : 0)
            }
            .animation(.spring(response: 0.5, dampingFraction: 0.6), value: showCheckmark)

            Text("Transaction Saved!")
                .font(.roundedTitle)
                .foregroundStyle(Color.textPrimary)

            Text("Your expense has been logged successfully.")
                .font(.roundedBody)
                .foregroundStyle(Color.textSecondary)
                .multilineTextAlignment(.center)

            Spacer()

            Button {
                onDismiss()
            } label: {
                Text("Done")
                    .font(.roundedHeadline)
                    .foregroundStyle(Color.appBackground)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 16)
                    .background(Color.accent)
                    .clipShape(RoundedRectangle(cornerRadius: 14))
            }
        }
        .padding(24)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color.appBackground)
        .onAppear {
            showCheckmark = true
        }
    }
}
