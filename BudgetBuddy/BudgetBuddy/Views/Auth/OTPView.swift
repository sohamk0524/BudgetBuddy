//
//  OTPView.swift
//  BudgetBuddy
//
//  OTP verification view with 6 digit input
//

import SwiftUI
import UIKit

struct OTPView: View {
    let phoneNumber: String

    @State private var otpDigits: [String] = Array(repeating: "", count: 6)
    @State private var focusedField: Int? = nil

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
                            isFocused: focusedField == index,
                            onBackspaceWhenEmpty: {
                                if index > 0 {
                                    otpDigits[index - 1] = ""
                                    focusedField = index - 1
                                }
                            },
                            onFullCode: { code in
                                let digits = code.filter { $0.isNumber }
                                for i in 0..<6 {
                                    otpDigits[i] = i < digits.count
                                        ? String(digits[digits.index(digits.startIndex, offsetBy: i)])
                                        : ""
                                }
                                focusedField = min(5, digits.count - 1)
                            }
                        )
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
        // Multi-char changes come from onFullCode (already handled) — ignore here
        if newValue.count > 1 { return }

        // Only allow digits (guard against non-numeric input)
        if !newValue.isEmpty && !newValue.allSatisfy({ $0.isNumber }) {
            otpDigits[index] = oldValue
            return
        }

        // Auto-advance to next field when a digit is entered
        if !newValue.isEmpty && index < 5 {
            focusedField = index + 1
        }

        // Auto-submit when all fields are filled
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
    let onBackspaceWhenEmpty: () -> Void
    let onFullCode: (String) -> Void

    var body: some View {
        BackspaceDetectingField(
            text: $digit,
            isFocused: isFocused,
            onBackspaceWhenEmpty: onBackspaceWhenEmpty,
            onFullCode: onFullCode
        )
        .frame(width: 48, height: 56)
        .background(Color.surface)
        .clipShape(RoundedRectangle(cornerRadius: 12))
        .overlay(
            RoundedRectangle(cornerRadius: 12)
                .stroke(isFocused ? Color.accent : Color.clear, lineWidth: 2)
        )
    }
}

// MARK: - UIKit-backed field (backspace detection + autofill spreading)

private struct BackspaceDetectingField: UIViewRepresentable {
    @Binding var text: String
    let isFocused: Bool
    let onBackspaceWhenEmpty: () -> Void
    let onFullCode: (String) -> Void

    func makeUIView(context: Context) -> BackspaceTextField {
        let tf = BackspaceTextField()
        tf.onDeleteWhenEmpty = onBackspaceWhenEmpty
        tf.delegate = context.coordinator
        tf.keyboardType = .numberPad
        tf.textContentType = .oneTimeCode
        tf.textAlignment = .center
        let base = UIFont.systemFont(ofSize: 24, weight: .bold)
        if let descriptor = base.fontDescriptor.withDesign(.rounded) {
            tf.font = UIFont(descriptor: descriptor, size: 24)
        } else {
            tf.font = base
        }
        return tf
    }

    func updateUIView(_ uiView: BackspaceTextField, context: Context) {
        if uiView.text != text {
            uiView.text = text
        }
        // Defer focus changes to avoid modifying view hierarchy during a SwiftUI update pass
        DispatchQueue.main.async {
            if isFocused && !uiView.isFirstResponder {
                uiView.becomeFirstResponder()
            } else if !isFocused && uiView.isFirstResponder {
                uiView.resignFirstResponder()
            }
        }
    }

    func makeCoordinator() -> Coordinator { Coordinator(self) }

    class Coordinator: NSObject, UITextFieldDelegate {
        var parent: BackspaceDetectingField
        init(_ parent: BackspaceDetectingField) { self.parent = parent }

        func textField(_ textField: UITextField,
                       shouldChangeCharactersIn range: NSRange,
                       replacementString string: String) -> Bool {
            let digits = string.filter { $0.isNumber }

            // Full OTP autofill (e.g. iOS SMS suggestion pastes "123456")
            if digits.count >= 6 {
                DispatchQueue.main.async { self.parent.onFullCode(digits) }
                return false
            }

            // Single digit or backspace
            parent.text = String(digits.prefix(1))
            return false
        }
    }
}

// MARK: - Backspace-aware UITextField

class BackspaceTextField: UITextField {
    var onDeleteWhenEmpty: (() -> Void)?

    override func deleteBackward() {
        if (text ?? "").isEmpty {
            onDeleteWhenEmpty?()
        }
        super.deleteBackward()
    }
}

// MARK: - Preview

#Preview {
    OTPView(phoneNumber: "+14155551234")
}
