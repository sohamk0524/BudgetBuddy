//
//  AuthManager.swift
//  BudgetBuddy
//
//  Manages user authentication state and API calls for SMS-based auth
//

import SwiftUI
import Observation

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
        if case .authenticated = authState {
            return true
        }
        return false
    }

    var authToken: Int? {
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

    /// For physical devices, change to your Mac's IP address (run: ipconfig getifaddr en0)
    private let baseURL = URL(string: "http://localhost:5000")!

    /// Ephemeral session to avoid caching issues
    @ObservationIgnored
    private var session: URLSession = {
        let config = URLSessionConfiguration.ephemeral
        config.httpShouldUsePipelining = false
        return URLSession(configuration: config)
    }()

    init() {
        // Restore cached values for immediate UI — restoreSession() validates with backend
        if let token = UserDefaults.standard.value(forKey: "authToken") as? Int {
            self.authToken = token
            self.authState = .authenticated
        }
        if let name = UserDefaults.standard.string(forKey: "userName") {
            self.userName = name
        }
    }

    // MARK: - Session Restore

    /// Validates the saved token against the backend and refreshes user state.
    /// Call once on app launch when a persisted token exists.
    func restoreSession() async {
        guard let userId = authToken else { return }

        do {
            let url = baseURL.appendingPathComponent("user/profile/\(userId)")
            let (data, response) = try await URLSession.shared.data(from: url)

            guard let httpResponse = response as? HTTPURLResponse else {
                throw AuthError.invalidResponse
            }

            if httpResponse.statusCode == 200 {
                let json = try JSONSerialization.jsonObject(with: data) as? [String: Any]
                let name = json?["name"] as? String
                let hasProfile = json?["profile"] != nil && !(json?["profile"] is NSNull)

                await MainActor.run {
                    self.userName = name
                    self.needsOnboarding = !hasProfile
                    self.authState = .authenticated
                }
            } else {
                // User no longer exists on backend — clear local session
                await MainActor.run {
                    self.signOut()
                }
            }
        } catch {
            // Network error — keep existing session so the app is usable offline
            print("Session restore failed: \(error)")
        }
    }

    // MARK: - Send Verification Code

    func sendCode(phoneNumber: String) async {
        await MainActor.run {
            isLoading = true
            errorMessage = nil
        }

        do {
            let url = baseURL.appendingPathComponent("v1/send_sms_code")
            var request = URLRequest(url: url)
            request.httpMethod = "POST"
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")

            let body: [String: Any] = [
                "phone_number": phoneNumber
            ]
            request.httpBody = try JSONSerialization.data(withJSONObject: body)

            let (data, response) = try await session.data(for: request)

            guard let httpResponse = response as? HTTPURLResponse else {
                throw AuthError.invalidResponse
            }

            // Try to parse JSON response
            let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any]

            if httpResponse.statusCode == 200 {
                await MainActor.run {
                    self.currentPhoneNumber = phoneNumber
                    self.authState = .verifyOTP(phoneNumber: phoneNumber)
                    self.isLoading = false
                }
            } else {
                let error = json?["error"] as? String ?? "Failed to send verification code (status: \(httpResponse.statusCode))"
                await MainActor.run {
                    self.errorMessage = error
                    self.isLoading = false
                }
            }
        } catch let urlError as URLError {
            await MainActor.run {
                self.errorMessage = self.friendlyErrorMessage(for: urlError)
                self.isLoading = false
            }
        } catch {
            await MainActor.run {
                self.errorMessage = "Connection failed. Is the server running?"
                self.isLoading = false
            }
        }
    }

    // MARK: - Verify Code

    func verifyCode(phoneNumber: String, code: String) async {
        await MainActor.run {
            isLoading = true
            errorMessage = nil
        }

        do {
            let url = baseURL.appendingPathComponent("v1/verify_code")
            var request = URLRequest(url: url)
            request.httpMethod = "POST"
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")

            let body: [String: Any] = [
                "phone_number": phoneNumber,
                "code": code
            ]
            request.httpBody = try JSONSerialization.data(withJSONObject: body)

            let (data, response) = try await session.data(for: request)

            guard let httpResponse = response as? HTTPURLResponse else {
                throw AuthError.invalidResponse
            }

            let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any]

            if httpResponse.statusCode == 200 {
                guard let token = json?["token"] as? Int,
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
                let error = json?["error"] as? String ?? "Verification failed"
                await MainActor.run {
                    self.errorMessage = error
                    self.isLoading = false
                }
            }
        } catch let urlError as URLError {
            await MainActor.run {
                self.errorMessage = self.friendlyErrorMessage(for: urlError)
                self.isLoading = false
            }
        } catch {
            await MainActor.run {
                self.errorMessage = "Connection failed. Is the server running?"
                self.isLoading = false
            }
        }
    }

    // MARK: - Error Helpers

    private func friendlyErrorMessage(for error: URLError) -> String {
        switch error.code {
        case .notConnectedToInternet:
            return "No internet connection"
        case .cannotConnectToHost, .cannotFindHost:
            return "Cannot connect to server. Make sure the backend is running."
        case .timedOut:
            return "Request timed out. Please try again."
        default:
            return "Network error: \(error.localizedDescription)"
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
            components.queryItems = [URLQueryItem(name: "userId", value: String(userId))]

            var request = URLRequest(url: components.url!)
            request.httpMethod = "DELETE"

            let (_, response) = try await session.data(for: request)

            guard let httpResponse = response as? HTTPURLResponse else {
                throw AuthError.invalidResponse
            }

            if httpResponse.statusCode == 204 {
                await MainActor.run {
                    self.signOut()
                }
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
        userBudgetingGoal: String = "stability",
        strictnessLevel: String = "moderate"
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
                "budgetingGoal": userBudgetingGoal,
                "strictnessLevel": strictnessLevel
            ]
            if !name.isEmpty {
                body["name"] = name
            }
            request.httpBody = try JSONSerialization.data(withJSONObject: body)

            let (data, response) = try await session.data(for: request)

            guard let httpResponse = response as? HTTPURLResponse else {
                throw AuthError.invalidResponse
            }

            if httpResponse.statusCode == 200 {
                await MainActor.run {
                    if !name.isEmpty {
                        self.userName = name
                    }
                    self.needsOnboarding = false
                    self.isLoading = false

                    // Post notification that onboarding completed
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
        authState = .enterPhone
        needsOnboarding = false
        authToken = nil
        userName = nil
        currentPhoneNumber = nil
        errorMessage = nil
        isLoading = false
        PlaidLinkManager.shared.reset()
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
