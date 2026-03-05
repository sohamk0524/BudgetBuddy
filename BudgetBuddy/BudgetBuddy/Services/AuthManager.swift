//
//  AuthManager.swift
//  BudgetBuddy
//
//  Manages user authentication state using Firebase Phone Auth.
//  Firebase handles the SMS OTP flow client-side; we exchange the
//  resulting ID token with our backend to get the app session.
//

import SwiftUI
import Observation
import FirebaseAuth

// MARK: - Auth State

enum AuthState: Equatable {
    case enterPhone
    case verifyOTP(phoneNumber: String)
    case authenticated
}

// MARK: - Auth Manager

@Observable
class AuthManager {
    static let shared = AuthManager()

    var authState: AuthState = .enterPhone
    var currentPhoneNumber: String?
    var needsOnboarding: Bool = false
    var isLoading: Bool = false
    var errorMessage: String?

    var isAuthenticated: Bool {
        if case .authenticated = authState { return true }
        return false
    }

    var authToken: String? {
        didSet {
            if let token = authToken {
                UserDefaults.standard.setValue(token, forKey: "authToken")
            } else {
                UserDefaults.standard.removeObject(forKey: "authToken")
            }
        }
    }

    var userName: String? {
        didSet {
            if let name = userName {
                UserDefaults.standard.setValue(name, forKey: "userName")
            } else {
                UserDefaults.standard.removeObject(forKey: "userName")
            }
        }
    }

    private let baseURL = AppConfig.baseURL

    @ObservationIgnored
    private var session: URLSession = {
        let config = URLSessionConfiguration.ephemeral
        config.httpShouldUsePipelining = false
        return URLSession(configuration: config)
    }()

    /// Firebase verification ID stored between sendCode and verifyCode steps
    @ObservationIgnored
    private var verificationID: String?

    init() {
        // Restore cached token for immediate UI — restoreSession() validates with Firebase
        if let token = UserDefaults.standard.string(forKey: "authToken") {
            self.authToken = token
            self.authState = .authenticated
        }
        if let name = UserDefaults.standard.string(forKey: "userName") {
            self.userName = name
        }
    }

    // MARK: - Session Restore

    /// On app launch, re-checks Firebase current user and refreshes backend profile.
    func restoreSession() async {
        guard Auth.auth().currentUser != nil, let userId = authToken else {
            await MainActor.run { self.signOut() }
            return
        }

        do {
            let url = baseURL.appendingPathComponent("user/profile/\(userId)")
            let (data, response) = try await URLSession.shared.data(from: url)

            guard let httpResponse = response as? HTTPURLResponse else { return }

            if httpResponse.statusCode == 200 {
                let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any]
                let name = json?["name"] as? String
                let hasProfile = json?["profile"] != nil && !(json?["profile"] is NSNull)
                await MainActor.run {
                    self.userName = name
                    self.needsOnboarding = !hasProfile
                    self.authState = .authenticated
                }
            } else {
                await MainActor.run { self.signOut() }
            }
        } catch {
            // Network error — keep existing session so the app is usable offline
            print("Session restore failed: \(error)")
        }
    }

    // MARK: - Send Verification Code (Firebase)

    func sendCode(phoneNumber: String) async {
        await MainActor.run {
            isLoading = true
            errorMessage = nil
        }

        do {
            let id = try await PhoneAuthProvider.provider().verifyPhoneNumber(phoneNumber, uiDelegate: nil)
            await MainActor.run {
                self.verificationID = id
                self.currentPhoneNumber = phoneNumber
                self.authState = .verifyOTP(phoneNumber: phoneNumber)
                self.isLoading = false
            }
        } catch {
            await MainActor.run {
                self.errorMessage = self.friendlyFirebaseError(error)
                self.isLoading = false
            }
        }
    }

    // MARK: - Verify Code (Firebase + Backend)

    func verifyCode(phoneNumber: String, code: String) async {
        await MainActor.run {
            isLoading = true
            errorMessage = nil
        }

        guard let verificationID else {
            await MainActor.run {
                self.errorMessage = "Session expired. Please request a new code."
                self.isLoading = false
            }
            return
        }

        do {
            // 1. Exchange code for Firebase credential
            let credential = PhoneAuthProvider.provider().credential(
                withVerificationID: verificationID,
                verificationCode: code
            )

            // 2. Sign in to Firebase
            let result = try await Auth.auth().signIn(with: credential)

            // 3. Get Firebase ID token and send to our backend
            let idToken = try await result.user.getIDToken()
            try await exchangeFirebaseToken(idToken)

        } catch let authError as NSError where authError.domain == AuthErrorDomain {
            await MainActor.run {
                self.errorMessage = self.friendlyFirebaseError(authError)
                self.isLoading = false
            }
        } catch {
            await MainActor.run {
                self.errorMessage = error.localizedDescription
                self.isLoading = false
            }
        }
    }

    // MARK: - Backend Token Exchange

    private func exchangeFirebaseToken(_ idToken: String) async throws {
        let url = baseURL.appendingPathComponent("v1/auth/firebase")
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONSerialization.data(withJSONObject: ["idToken": idToken])

        let (data, response) = try await session.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse else {
            throw AuthError.invalidResponse
        }

        let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any]

        if httpResponse.statusCode == 200 {
            guard let token = json?["token"] as? String,
                  let hasProfile = json?["hasProfile"] as? Bool else {
                throw AuthError.invalidResponse
            }
            let name = json?["name"] as? String
            await MainActor.run {
                self.authToken = token
                self.userName = name
                self.authState = .authenticated
                self.needsOnboarding = !hasProfile
                self.isLoading = false
            }
        } else {
            let message = json?["error"] as? String ?? "Authentication failed"
            await MainActor.run {
                self.errorMessage = message
                self.isLoading = false
            }
        }
    }

    // MARK: - Delete Account

    func deleteAccount() async {
        guard let userId = authToken else { return }

        await MainActor.run {
            isLoading = true
            errorMessage = nil
        }

        do {
            var components = URLComponents(url: baseURL.appendingPathComponent("v1/user"), resolvingAgainstBaseURL: false)!
            components.queryItems = [URLQueryItem(name: "userId", value: userId)]

            var request = URLRequest(url: components.url!)
            request.httpMethod = "DELETE"

            let (_, response) = try await session.data(for: request)

            guard let httpResponse = response as? HTTPURLResponse else {
                throw AuthError.invalidResponse
            }

            if httpResponse.statusCode == 204 {
                try? Auth.auth().signOut()
                await MainActor.run { self.signOut() }
            } else {
                await MainActor.run {
                    self.errorMessage = "Failed to delete account"
                    self.isLoading = false
                }
            }
        } catch {
            await MainActor.run {
                self.errorMessage = error.localizedDescription
                self.isLoading = false
            }
        }
    }

    // MARK: - Navigation

    func goBackToPhoneEntry() {
        authState = .enterPhone
        errorMessage = nil
    }

    // MARK: - Complete Onboarding

    func completeOnboarding(
        name: String = "",
        isStudent: Bool = false,
        weeklySpendingLimit: Double = 0,
        strictnessLevel: String = "moderate",
        school: String = ""
    ) async {
        guard let userId = authToken else { return }

        await MainActor.run {
            isLoading = true
            errorMessage = nil
        }

        do {
            let url = baseURL.appendingPathComponent("onboarding")
            var request = URLRequest(url: url)
            request.httpMethod = "POST"
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")

            var body: [String: Any] = [
                "userId": userId,
                "isStudent": isStudent,
                "weeklySpendingLimit": weeklySpendingLimit,
                "strictnessLevel": strictnessLevel
            ]
            if !name.isEmpty { body["name"] = name }
            if !school.isEmpty { body["school"] = school }
            request.httpBody = try JSONSerialization.data(withJSONObject: body)

            let (data, response) = try await session.data(for: request)

            guard let httpResponse = response as? HTTPURLResponse else {
                throw AuthError.invalidResponse
            }

            if httpResponse.statusCode == 200 {
                await MainActor.run {
                    if !name.isEmpty { self.userName = name }
                    self.needsOnboarding = false
                    self.isLoading = false
                    NotificationCenter.default.post(name: .onboardingCompleted, object: nil)
                }
            } else {
                let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any]
                let error = json?["error"] as? String ?? "Onboarding failed"
                await MainActor.run {
                    self.errorMessage = error
                    self.isLoading = false
                }
            }
        } catch {
            await MainActor.run {
                self.errorMessage = error.localizedDescription
                self.isLoading = false
            }
        }
    }

    // MARK: - Sign Out

    func signOut() {
        try? Auth.auth().signOut()
        authState = .enterPhone
        needsOnboarding = false
        authToken = nil
        userName = nil
        currentPhoneNumber = nil
        verificationID = nil
        errorMessage = nil
        isLoading = false
        PlaidLinkManager.shared.reset()
    }

    // MARK: - Error Helpers

    private func friendlyFirebaseError(_ error: Error) -> String {
        let nsError = error as NSError
        guard nsError.domain == AuthErrorDomain else {
            return error.localizedDescription
        }
        switch AuthErrorCode(rawValue: nsError.code) {
        case .invalidPhoneNumber:
            return "Invalid phone number. Please include country code (e.g. +1)."
        case .invalidVerificationCode:
            return "Incorrect code. Please try again."
        case .sessionExpired:
            return "Code expired. Please request a new one."
        case .tooManyRequests:
            return "Too many attempts. Please wait and try again."
        case .networkError:
            return "No internet connection."
        default:
            return nsError.localizedDescription
        }
    }
}

// MARK: - Auth Errors

enum AuthError: LocalizedError {
    case invalidResponse
    case serverError(String)

    var errorDescription: String? {
        switch self {
        case .invalidResponse:
            return "Invalid response from server"
        case .serverError(let message):
            return message
        }
    }
}
