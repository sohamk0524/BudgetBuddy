//
//  BiometricUnlockView.swift
//  BudgetBuddy
//
//  Lock screen shown on app relaunch when biometric auth is enabled.
//  Also contains BiometricSetupSheet used during onboarding.
//

import SwiftUI

// MARK: - Biometric Unlock Screen

struct BiometricUnlockView: View {
    var authManager = AuthManager.shared

    private var biometricIcon: String {
        authManager.biometricType == "Face ID" ? "faceid" : "touchid"
    }

    var body: some View {
        ZStack {
            Color.appBackground.ignoresSafeArea()

            VStack(spacing: 0) {
                Spacer()

                VStack(spacing: 16) {
                    Image(systemName: "wallet.pass.fill")
                        .font(.system(size: 64))
                        .foregroundStyle(Color.accent)

                    Text("BudgetBuddy")
                        .font(.roundedLargeTitle)
                        .foregroundStyle(Color.textPrimary)

                    Text("Your AI Financial Copilot")
                        .font(.roundedBody)
                        .foregroundStyle(Color.textSecondary)
                }

                Spacer()

                VStack(spacing: 16) {
                    Button {
                        Task { await authManager.authenticateWithBiometrics() }
                    } label: {
                        HStack(spacing: 10) {
                            Image(systemName: biometricIcon)
                                .font(.title3)
                            Text("Unlock with \(authManager.biometricType)")
                                .font(.roundedHeadline)
                        }
                        .foregroundStyle(Color.appBackground)
                        .frame(maxWidth: .infinity)
                        .padding()
                        .background(Color.accent)
                        .clipShape(RoundedRectangle(cornerRadius: 12))
                    }
                    .padding(.horizontal, 24)

                    if let error = authManager.errorMessage {
                        Text(error)
                            .font(.roundedCaption)
                            .foregroundStyle(Color.danger)
                            .multilineTextAlignment(.center)
                            .padding(.horizontal)
                    }

                    Button("Use Phone Number Instead") {
                        authManager.signOut()
                    }
                    .font(.roundedBody)
                    .foregroundStyle(Color.textSecondary)
                }
                .padding(.bottom, 48)
            }
        }
        .task {
            await authManager.authenticateWithBiometrics()
        }
    }
}

// MARK: - Biometric Setup Sheet (shown during onboarding)

struct BiometricSetupSheet: View {
    var authManager = AuthManager.shared
    let onComplete: () -> Void

    private var biometricIcon: String {
        authManager.biometricType == "Face ID" ? "faceid" : "touchid"
    }

    var body: some View {
        ZStack {
            Color.appBackground.ignoresSafeArea()

            VStack(spacing: 32) {
                Spacer()

                Image(systemName: biometricIcon)
                    .font(.system(size: 64))
                    .foregroundStyle(Color.accent)

                VStack(spacing: 12) {
                    Text("Enable \(authManager.biometricType)?")
                        .font(.roundedTitle)
                        .foregroundStyle(Color.textPrimary)

                    Text("Unlock BudgetBuddy instantly without a verification code. Your biometric data never leaves your device — it's stored securely in your phone's Secure Enclave.")
                        .font(.roundedBody)
                        .foregroundStyle(Color.textSecondary)
                        .multilineTextAlignment(.center)
                        .padding(.horizontal, 32)
                }

                Spacer()

                VStack(spacing: 12) {
                    Button {
                        Task {
                            _ = await authManager.enableBiometrics()
                            onComplete()
                        }
                    } label: {
                        HStack(spacing: 10) {
                            Image(systemName: biometricIcon)
                                .font(.title3)
                            Text("Enable \(authManager.biometricType)")
                                .font(.roundedHeadline)
                        }
                        .foregroundStyle(Color.appBackground)
                        .frame(maxWidth: .infinity)
                        .padding()
                        .background(Color.accent)
                        .clipShape(RoundedRectangle(cornerRadius: 12))
                    }

                    Button("Skip for Now") {
                        onComplete()
                    }
                    .font(.roundedBody)
                    .foregroundStyle(Color.textSecondary)
                }
                .padding(.horizontal, 24)
                .padding(.bottom, 48)
            }
        }
    }
}
