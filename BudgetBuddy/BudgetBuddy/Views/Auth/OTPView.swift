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

    @State private var codeString: String = ""
    @State private var isFieldFocused: Bool = false

    var authManager = AuthManager.shared

    private var otpDigits: [String] {
        var result = Array(repeating: "", count: 6)
        for (i, char) in codeString.prefix(6).enumerated() {
            result[i] = String(char)
        }
        return result
    }

    private var isComplete: Bool { codeString.count == 6 }

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

                // OTP Input — 6 display boxes over a single hidden text field
                ZStack {
                    HStack(spacing: 12) {
                        ForEach(0..<6, id: \.self) { index in
                            ZStack {
                                RoundedRectangle(cornerRadius: 12)
                                    .fill(Color.surface)
                                    .overlay(
                                        RoundedRectangle(cornerRadius: 12)
                                            .stroke(
                                                isFieldFocused && index == min(5, codeString.count)
                                                    ? Color.accent : Color.clear,
                                                lineWidth: 2
                                            )
                                    )
                                if index < otpDigits.count, !otpDigits[index].isEmpty {
                                    Text(otpDigits[index])
                                        .font(.system(size: 24, weight: .bold, design: .rounded))
                                        .foregroundStyle(Color.textPrimary)
                                }
                            }
                            .frame(width: 48, height: 56)
                        }
                    }

                    // Invisible unified input field — receives all typing and autofill
                    OTPHiddenTextField(codeString: $codeString, isFocused: $isFieldFocused)
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                        .opacity(0.01)
                }
                .frame(height: 56)
                .padding(.horizontal, 24)
                .padding(.top, 24)
                .onTapGesture { isFieldFocused = true }
                .onChange(of: codeString) { _, newCode in
                    if newCode.count == 6 && !authManager.isLoading {
                        isFieldFocused = false
                        Task {
                            await authManager.verifyCode(phoneNumber: phoneNumber, code: newCode)
                        }
                    }
                }

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
                        codeString = ""
                        isFieldFocused = true
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
            isFieldFocused = true
        }
    }
}

// MARK: - Hidden unified text field

private struct OTPHiddenTextField: UIViewRepresentable {
    @Binding var codeString: String
    @Binding var isFocused: Bool

    func makeUIView(context: Context) -> UITextField {
        let tf = UITextField()
        tf.keyboardType = .numberPad
        tf.textContentType = .oneTimeCode
        tf.autocorrectionType = .no
        tf.tintColor = .clear   // hide blinking cursor
        tf.textColor = .clear   // hide rendered text
        tf.delegate = context.coordinator
        return tf
    }

    func updateUIView(_ uiView: UITextField, context: Context) {
        if uiView.text != codeString {
            uiView.text = codeString
        }
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
        var parent: OTPHiddenTextField
        init(_ p: OTPHiddenTextField) { parent = p }

        func textField(_ textField: UITextField,
                       shouldChangeCharactersIn range: NSRange,
                       replacementString string: String) -> Bool {
            let current = textField.text ?? ""
            let newCode: String
            if string.isEmpty {
                // Backspace
                newCode = String(current.dropLast())
            } else {
                let digits = string.filter { $0.isNumber }
                newCode = String((current + digits).prefix(6))
            }
            textField.text = newCode
            parent.codeString = newCode
            return false
        }
    }
}

// MARK: - Preview

#Preview {
    OTPView(phoneNumber: "+14155551234")
}
