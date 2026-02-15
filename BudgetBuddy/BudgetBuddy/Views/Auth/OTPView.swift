//
//  OTPView.swift
//  BudgetBuddy
//
//  OTP verification view with 6 digit input
//

import SwiftUI

struct OTPView: View {
    let phoneNumber: String

    @State private var otpDigits: [String] = Array(repeating: "", count: 6)
    @FocusState private var focusedField: Int?

    var authManager = AuthManager.shared

    private var otpCode: String {
        otpDigits.joined()
    }

    private var isComplete: Bool {
        otpDigits.allSatisfy { !$0.isEmpty }
    }

    private var maskedPhone: String {
        guard phoneNumber.count >= 4 else { return phoneNumber }
        let lastFour = String(phoneNumber.suffix(4))
        return "(...) *** - \(lastFour)"
    }

    var body: some View {
        ZStack {
            Color.appBackground
                .ignoresSafeArea()

            VStack(spacing: 24) {
                // Back Button
                HStack {
                    Button {
                        authManager.goBackToPhoneEntry()
                    } label: {
                        HStack(spacing: 4) {
                            Image(systemName: "chevron.left")
                            Text("Back")
                        }
                        .font(.roundedBody)
                        .foregroundStyle(Color.accent)
                    }
                    Spacer()
                }
                .padding(.horizontal, 24)
                .padding(.top, 16)

                Spacer()

                // Title
                VStack(spacing: 12) {
                    Text("Enter verification code")
                        .font(.roundedTitle)
                        .foregroundStyle(Color.textPrimary)

                    Text("We sent a code to \(maskedPhone)")
                        .font(.roundedBody)
                        .foregroundStyle(Color.textSecondary)
                }

                // OTP Input Fields
                HStack(spacing: 12) {
                    ForEach(0..<6, id: \.self) { index in
                        OTPDigitField(
                            digit: $otpDigits[index],
                            isFocused: focusedField == index
                        )
                        .focused($focusedField, equals: index)
                        .onChange(of: otpDigits[index]) { oldValue, newValue in
                            handleDigitChange(index: index, oldValue: oldValue, newValue: newValue)
                        }
                    }
                }
                .padding(.horizontal, 24)
                .padding(.top, 24)

                // Error Message
                if let error = authManager.errorMessage {
                    Text(error)
                        .font(.roundedCaption)
                        .foregroundStyle(Color.danger)
                        .multilineTextAlignment(.center)
                        .padding(.horizontal)
                }

                // Loading indicator
                if authManager.isLoading {
                    ProgressView()
                        .tint(Color.accent)
                        .padding()
                }

                // Resend Code Button
                Button {
                    Task {
                        // Clear digits
                        otpDigits = Array(repeating: "", count: 6)
                        focusedField = 0
                        await authManager.sendCode(phoneNumber: phoneNumber)
                    }
                } label: {
                    Text("Resend code")
                        .font(.roundedBody)
                        .foregroundStyle(Color.accent)
                }
                .disabled(authManager.isLoading)
                .padding(.top, 16)

                Spacer()
                Spacer()
            }
        }
        .onAppear {
            focusedField = 0
        }
    }

    private func handleDigitChange(index: Int, oldValue: String, newValue: String) {
        // Only allow single digit
        if newValue.count > 1 {
            otpDigits[index] = String(newValue.suffix(1))
            return
        }

        // Only allow digits
        if !newValue.isEmpty && !newValue.allSatisfy({ $0.isNumber }) {
            otpDigits[index] = oldValue
            return
        }

        // Auto-advance to next field
        if !newValue.isEmpty && index < 5 {
            focusedField = index + 1
        }

        // Auto-submit when complete
        if isComplete && !authManager.isLoading {
            Task {
                await authManager.verifyCode(phoneNumber: phoneNumber, code: otpCode)
            }
        }
    }
}

// MARK: - OTP Digit Field

struct OTPDigitField: View {
    @Binding var digit: String
    let isFocused: Bool

    var body: some View {
        TextField("", text: $digit)
            .keyboardType(.numberPad)
            .textContentType(.oneTimeCode)
            .multilineTextAlignment(.center)
            .font(.system(size: 24, weight: .bold, design: .rounded))
            .foregroundStyle(Color.textPrimary)
            .frame(width: 48, height: 56)
            .background(Color.surface)
            .clipShape(RoundedRectangle(cornerRadius: 12))
            .overlay(
                RoundedRectangle(cornerRadius: 12)
                    .stroke(isFocused ? Color.accent : Color.clear, lineWidth: 2)
            )
    }
}

// MARK: - Preview

#Preview {
    OTPView(phoneNumber: "+14155551234")
}
