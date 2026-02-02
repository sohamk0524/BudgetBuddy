//
//  LoginView.swift
//  BudgetBuddy
//
//  Login and registration view
//

import SwiftUI

struct LoginView: View {
    @State private var email: String = ""
    @State private var password: String = ""
    @State private var isRegistering: Bool = false

    var authManager = AuthManager.shared

    var body: some View {
        ZStack {
            Color.background
                .ignoresSafeArea()

            VStack(spacing: 32) {
                // Logo and Title
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
                .padding(.bottom, 24)

                // Input Fields
                VStack(spacing: 16) {
                    // Email Field
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Email")
                            .font(.roundedCaption)
                            .foregroundStyle(Color.textSecondary)

                        TextField("you@example.com", text: $email)
                            .textFieldStyle(.plain)
                            .font(.roundedBody)
                            .foregroundStyle(Color.textPrimary)
                            .autocapitalization(.none)
                            .keyboardType(.emailAddress)
                            .textContentType(.emailAddress)
                            .padding()
                            .background(Color.surface)
                            .clipShape(RoundedRectangle(cornerRadius: 12))
                    }

                    // Password Field
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Password")
                            .font(.roundedCaption)
                            .foregroundStyle(Color.textSecondary)

                        SecureField("Enter password", text: $password)
                            .textFieldStyle(.plain)
                            .font(.roundedBody)
                            .foregroundStyle(Color.textPrimary)
                            .textContentType(isRegistering ? .newPassword : .password)
                            .padding()
                            .background(Color.surface)
                            .clipShape(RoundedRectangle(cornerRadius: 12))
                    }
                }
                .padding(.horizontal, 24)

                // Error Message
                if let error = authManager.errorMessage {
                    Text(error)
                        .font(.roundedCaption)
                        .foregroundStyle(Color.danger)
                        .multilineTextAlignment(.center)
                        .padding(.horizontal)
                }

                // Buttons
                VStack(spacing: 16) {
                    // Primary Button (Sign In / Register)
                    Button {
                        Task {
                            if isRegistering {
                                await authManager.register(email: email, password: password)
                            } else {
                                await authManager.login(email: email, password: password)
                            }
                        }
                    } label: {
                        if authManager.isLoading {
                            ProgressView()
                                .tint(Color.background)
                                .frame(maxWidth: .infinity)
                                .padding()
                        } else {
                            Text(isRegistering ? "Create Account" : "Sign In")
                                .font(.roundedHeadline)
                                .foregroundStyle(Color.background)
                                .frame(maxWidth: .infinity)
                                .padding()
                        }
                    }
                    .background(Color.accent)
                    .clipShape(RoundedRectangle(cornerRadius: 12))
                    .disabled(email.isEmpty || password.isEmpty || authManager.isLoading)
                    .opacity((email.isEmpty || password.isEmpty) ? 0.6 : 1.0)

                    // Toggle between Sign In and Register
                    Button {
                        withAnimation {
                            isRegistering.toggle()
                            authManager.errorMessage = nil
                        }
                    } label: {
                        Text(isRegistering ? "Already have an account? Sign In" : "Don't have an account? Register")
                            .font(.roundedCaption)
                            .foregroundStyle(Color.accent)
                    }
                }
                .padding(.horizontal, 24)

                Spacer()
            }
            .padding(.top, 60)
        }
    }
}

// MARK: - Preview

#Preview {
    LoginView()
}
