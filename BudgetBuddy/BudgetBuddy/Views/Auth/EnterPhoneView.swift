//
//  EnterPhoneView.swift
//  BudgetBuddy
//
//  Phone number entry for SMS authentication
//

import SwiftUI
import PhoneNumberKit
import SafariServices

struct EnterPhoneView: View {
    @State private var phoneNumber: String = ""
    @State private var selectedCountry: Country = .us

    var authManager = AuthManager.shared

//    private let phoneNumberKit = PhoneNumberKit()

    private var digitsOnly: String {
        phoneNumber.filter { $0.isNumber }
    }

    private var isValidPhone: Bool {
        // For US, need 10 digits
        if selectedCountry == .us {
            return digitsOnly.count == 10
        }
        // For other countries, at least 8 digits
        return digitsOnly.count >= 8
    }

    private var e164Number: String {
        "+\(selectedCountry.dialCode)\(digitsOnly)"
    }

    var body: some View {
        ZStack {
            Color.appBackground
                .ignoresSafeArea()

            VStack(spacing: 32) {
                Spacer()

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

                // Phone Number Field
                VStack(alignment: .leading, spacing: 8) {
                    Text("Phone Number")
                        .font(.roundedCaption)
                        .foregroundStyle(Color.textSecondary)

                    HStack(spacing: 12) {
                        // Country Picker
                        Menu {
                            ForEach(Country.allCases) { country in
                                Button {
                                    selectedCountry = country
                                } label: {
                                    Text("\(country.flag) \(country.name) (+\(country.dialCode))")
                                }
                            }
                        } label: {
                            HStack(spacing: 4) {
                                Text(selectedCountry.flag)
                                    .font(.title2)
                                Text("+\(selectedCountry.dialCode)")
                                    .font(.roundedBody)
                                    .foregroundStyle(Color.textPrimary)
                                Image(systemName: "chevron.down")
                                    .font(.caption)
                                    .foregroundStyle(Color.textSecondary)
                            }
                            .padding(.horizontal, 12)
                            .padding(.vertical, 14)
                            .background(Color.surface)
                            .clipShape(RoundedRectangle(cornerRadius: 12))
                        }

                        // Phone Number Input
                        TextField("(555) 123-4567", text: $phoneNumber)
                            .textFieldStyle(.plain)
                            .font(.roundedBody)
                            .foregroundStyle(Color.textPrimary)
                            .keyboardType(.phonePad)
                            .textContentType(.telephoneNumber)
                            .padding()
                            .background(Color.surface)
                            .clipShape(RoundedRectangle(cornerRadius: 12))
                            .onChange(of: phoneNumber) { _, newValue in
                                phoneNumber = formatPhoneNumber(newValue)
                            }
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

                // Continue Button
                Button {
                    Task {
                        await authManager.sendCode(phoneNumber: e164Number)
                    }
                } label: {
                    if authManager.isLoading {
                        ProgressView()
                            .tint(Color.appBackground)
                            .frame(maxWidth: .infinity)
                            .padding()
                    } else {
                        Text("Continue")
                            .font(.roundedHeadline)
                            .foregroundStyle(Color.appBackground)
                            .frame(maxWidth: .infinity)
                            .padding()
                    }
                }
                .background(Color.accent)
                .clipShape(RoundedRectangle(cornerRadius: 12))
                .disabled(!isValidPhone || authManager.isLoading)
                .opacity(isValidPhone ? 1.0 : 0.6)
                .padding(.horizontal, 24)

                Spacer()

                // Terms Text
                Text("By continuing, you agree to our [Terms of Service](\(AppConfig.termsURL.absoluteString)) and [Privacy Policy](\(AppConfig.privacyURL.absoluteString))")
                    .font(.system(.caption2, design: .rounded))
                    .foregroundStyle(Color.textSecondary)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, 32)
                    .padding(.bottom, 16)
                    .environment(\.openURL, OpenURLAction { url in
                        let vc = SFSafariViewController(url: url)
                        UIApplication.shared.connectedScenes
                            .compactMap { $0 as? UIWindowScene }
                            .first?.windows.first?.rootViewController?
                            .present(vc, animated: true)
                        return .handled
                    })
            }
        }
    }

    /// Format phone number for display (US format)
    private func formatPhoneNumber(_ input: String) -> String {
        let digits = input.filter { $0.isNumber }

        // Limit to reasonable length
        let limited = String(digits.prefix(15))

        // For US, format as (XXX) XXX-XXXX
        if selectedCountry == .us {
            if limited.count <= 3 {
                return limited
            } else if limited.count <= 6 {
                let area = String(limited.prefix(3))
                let rest = String(limited.dropFirst(3))
                return "(\(area)) \(rest)"
            } else {
                let area = String(limited.prefix(3))
                let middle = String(limited.dropFirst(3).prefix(3))
                let last = String(limited.dropFirst(6).prefix(4))
                if last.isEmpty {
                    return "(\(area)) \(middle)"
                }
                return "(\(area)) \(middle)-\(last)"
            }
        }

        // For other countries, just return digits
        return limited
    }
}

// MARK: - Country Model

enum Country: String, CaseIterable, Identifiable {
    case us
    case ca
    case uk
    case mx
    case au
    case de
    case fr
    case jp
    case in_
    case br

    var id: String { rawValue }

    var name: String {
        switch self {
        case .us: return "United States"
        case .ca: return "Canada"
        case .uk: return "United Kingdom"
        case .mx: return "Mexico"
        case .au: return "Australia"
        case .de: return "Germany"
        case .fr: return "France"
        case .jp: return "Japan"
        case .in_: return "India"
        case .br: return "Brazil"
        }
    }

    var dialCode: String {
        switch self {
        case .us, .ca: return "1"
        case .uk: return "44"
        case .mx: return "52"
        case .au: return "61"
        case .de: return "49"
        case .fr: return "33"
        case .jp: return "81"
        case .in_: return "91"
        case .br: return "55"
        }
    }

    var flag: String {
        switch self {
        case .us: return "🇺🇸"
        case .ca: return "🇨🇦"
        case .uk: return "🇬🇧"
        case .mx: return "🇲🇽"
        case .au: return "🇦🇺"
        case .de: return "🇩🇪"
        case .fr: return "🇫🇷"
        case .jp: return "🇯🇵"
        case .in_: return "🇮🇳"
        case .br: return "🇧🇷"
        }
    }
}

// MARK: - Preview

#Preview {
    EnterPhoneView()
}
