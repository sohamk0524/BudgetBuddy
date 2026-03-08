//
//  LoginView.swift
//  BudgetBuddy
//
//  Auth router view - shows appropriate view based on auth state
//

import SwiftUI

struct LoginView: View {
    var authManager = AuthManager.shared

    var body: some View {
        switch authManager.authState {
        case .enterPhone:
            EnterPhoneView()

        case .verifyOTP(let phoneNumber):
            OTPView(phoneNumber: phoneNumber)

        case .biometricPrompt:
            BiometricUnlockView()

        case .authenticated:
            EmptyView()
        }
    }
}

// MARK: - Preview

#Preview {
    LoginView()
}
