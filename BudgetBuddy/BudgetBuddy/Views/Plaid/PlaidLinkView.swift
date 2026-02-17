//
//  PlaidLinkView.swift
//  BudgetBuddy
//
//  View for initiating Plaid Link to connect bank accounts
//

import SwiftUI

struct PlaidLinkView: View {
    @State private var plaidManager = PlaidLinkManager.shared
    @Binding var showPlaidLink: Bool

    let userId: Int
    let onComplete: () -> Void
    let onSkip: () -> Void

    var body: some View {
        ZStack {
            Color.appBackground.ignoresSafeArea()

            VStack(spacing: 24) {
                Spacer()

                // Icon
                Image(systemName: "building.columns.fill")
                    .font(.system(size: 60))
                    .foregroundStyle(Color.accent)
                    .padding(.bottom, 8)

                // Title
                Text("Connect Your Bank")
                    .font(.system(.title, design: .rounded, weight: .bold))
                    .foregroundStyle(Color.textPrimary)

                // Description
                Text("Securely link your bank accounts to automatically import your transactions and get personalized insights.")
                    .font(.system(.body, design: .rounded))
                    .foregroundStyle(Color.textSecondary)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, 32)

                // Security badges
                HStack(spacing: 16) {
                    SecurityBadge(icon: "lock.shield.fill", text: "Bank-level security")
                    SecurityBadge(icon: "eye.slash.fill", text: "Read-only access")
                }
                .padding(.top, 8)

                Spacer()

                // Error message
                if let error = plaidManager.errorMessage {
                    Text(error)
                        .font(.system(.caption, design: .rounded))
                        .foregroundStyle(.red)
                        .multilineTextAlignment(.center)
                        .padding(.horizontal)
                }

                // Success message
                if plaidManager.linkSuccess {
                    VStack(spacing: 8) {
                        Image(systemName: "checkmark.circle.fill")
                            .font(.system(size: 48))
                            .foregroundStyle(.green)

                        Text("Bank Connected!")
                            .font(.system(.headline, design: .rounded, weight: .semibold))
                            .foregroundStyle(Color.textPrimary)

                        if !plaidManager.linkedAccounts.isEmpty {
                            Text("\(plaidManager.linkedAccounts.count) account(s) linked")
                                .font(.system(.subheadline, design: .rounded))
                                .foregroundStyle(Color.textSecondary)
                        }
                    }
                    .padding()
                    .onAppear {
                        // Auto-dismiss after success
                        DispatchQueue.main.asyncAfter(deadline: .now() + 1.5) {
                            onComplete()
                        }
                    }
                }

                // Connect button
                if !plaidManager.linkSuccess {
                    Button {
                        Task {
                            await plaidManager.startLink(userId: userId)
                        }
                    } label: {
                        HStack {
                            if plaidManager.isLoading {
                                ProgressView()
                                    .tint(.white)
                            } else {
                                Image(systemName: "link")
                                Text("Connect Bank Account")
                            }
                        }
                        .frame(maxWidth: .infinity)
                        .padding()
                        .background(Color.accent)
                        .foregroundStyle(.white)
                        .font(.system(.headline, design: .rounded, weight: .semibold))
                        .clipShape(RoundedRectangle(cornerRadius: 12))
                    }
                    .disabled(plaidManager.isLoading)
                    .padding(.horizontal, 24)

                    // Skip button
                    Button {
                        onSkip()
                    } label: {
                        Text("Skip for now")
                            .font(.system(.subheadline, design: .rounded))
                            .foregroundStyle(Color.textSecondary)
                    }
                    .padding(.top, 8)
                }

                Spacer()
                    .frame(height: 40)
            }
        }
        .onAppear {
            plaidManager.reset()
        }
        .sheet(isPresented: Binding(
            get: { plaidManager.isLinkActive },
            set: { _ in }
        )) {
            PlaidLinkSheetView(userId: userId, manager: plaidManager)
        }
    }
}

// MARK: - Security Badge

private struct SecurityBadge: View {
    let icon: String
    let text: String

    var body: some View {
        HStack(spacing: 6) {
            Image(systemName: icon)
                .font(.system(size: 12))
            Text(text)
                .font(.system(.caption, design: .rounded))
        }
        .foregroundStyle(Color.textSecondary)
        .padding(.horizontal, 12)
        .padding(.vertical, 6)
        .background(Color.surface)
        .clipShape(RoundedRectangle(cornerRadius: 8))
    }
}

// MARK: - Plaid Link Sheet

struct PlaidLinkSheetView: UIViewControllerRepresentable {
    let userId: Int
    let manager: PlaidLinkManager

    func makeUIViewController(context: Context) -> UIViewController {
        let viewController = UIViewController()
        viewController.view.backgroundColor = .clear

        DispatchQueue.main.async {
            manager.presentLink(from: viewController, userId: userId) { success in
                // Link completion handled by manager
            }
        }

        return viewController
    }

    func updateUIViewController(_ uiViewController: UIViewController, context: Context) {}
}

// MARK: - Preview

#Preview {
    PlaidLinkView(
        showPlaidLink: .constant(true),
        userId: 1,
        onComplete: {},
        onSkip: {}
    )
}
