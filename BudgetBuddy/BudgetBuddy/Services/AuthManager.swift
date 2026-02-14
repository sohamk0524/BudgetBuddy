//
//  AuthManager.swift
//  BudgetBuddy
//
//  Manages user authentication state and API calls
//

import SwiftUI
import Observation

@Observable
class AuthManager {
    static let shared = AuthManager()

    var isAuthenticated: Bool = false
    var needsOnboarding: Bool = false
    var isLoading: Bool = false
    var errorMessage: String?

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

    init() {
        // Restore cached values for immediate UI — restoreSession() validates with backend
        if let token = UserDefaults.standard.value(forKey: "authToken") as? Int {
            self.authToken = token
            self.isAuthenticated = true
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
                    self.isAuthenticated = true
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

    // MARK: - Login

    func login(email: String, password: String) async {
        await MainActor.run {
            isLoading = true
            errorMessage = nil
        }

        do {
            let url = baseURL.appendingPathComponent("login")
            var request = URLRequest(url: url)
            request.httpMethod = "POST"
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")

            let body: [String: Any] = [
                "email": email,
                "password": password
            ]
            request.httpBody = try JSONSerialization.data(withJSONObject: body)

            let (data, response) = try await URLSession.shared.data(for: request)

            guard let httpResponse = response as? HTTPURLResponse else {
                throw AuthError.invalidResponse
            }

            let json = try JSONSerialization.jsonObject(with: data) as? [String: Any]

            if httpResponse.statusCode == 200 {
                guard let token = json?["token"] as? Int,
                      let hasProfile = json?["hasProfile"] as? Bool else {
                    throw AuthError.invalidResponse
                }

                let name = json?["name"] as? String

                await MainActor.run {
                    self.authToken = token
                    self.userName = name
                    self.isAuthenticated = true
                    self.needsOnboarding = !hasProfile
                    self.isLoading = false
                }
            } else {
                let error = json?["error"] as? String ?? "Login failed"
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

    // MARK: - Register

    func register(email: String, password: String) async {
        await MainActor.run {
            isLoading = true
            errorMessage = nil
        }

        do {
            let url = baseURL.appendingPathComponent("register")
            var request = URLRequest(url: url)
            request.httpMethod = "POST"
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")

            let body: [String: Any] = [
                "email": email,
                "password": password
            ]
            request.httpBody = try JSONSerialization.data(withJSONObject: body)

            let (data, response) = try await URLSession.shared.data(for: request)

            guard let httpResponse = response as? HTTPURLResponse else {
                throw AuthError.invalidResponse
            }

            let json = try JSONSerialization.jsonObject(with: data) as? [String: Any]

            if httpResponse.statusCode == 200 {
                guard let token = json?["token"] as? Int else {
                    throw AuthError.invalidResponse
                }

                await MainActor.run {
                    self.authToken = token
                    self.isAuthenticated = true
                    self.needsOnboarding = true
                    self.isLoading = false
                }
            } else {
                let error = json?["error"] as? String ?? "Registration failed"
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

    // MARK: - Complete Onboarding

    func completeOnboarding(
        name: String = "",
        age: Int,
        occupation: String,
        income: Double,
        incomeFrequency: String = "monthly",
        financialPersonality: String = "balanced",
        primaryGoal: String = "stability"
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
                "age": age,
                "occupation": occupation,
                "income": income,
                "incomeFrequency": incomeFrequency,
                "financialPersonality": financialPersonality,
                "primaryGoal": primaryGoal
            ]
            if !name.isEmpty {
                body["name"] = name
            }
            request.httpBody = try JSONSerialization.data(withJSONObject: body)

            let (data, response) = try await URLSession.shared.data(for: request)

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
        isAuthenticated = false
        needsOnboarding = false
        authToken = nil
        userName = nil
        errorMessage = nil
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
