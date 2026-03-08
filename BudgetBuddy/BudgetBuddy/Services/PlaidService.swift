//
//  PlaidService.swift
//  BudgetBuddy
//
//  Actor-isolated service for Plaid API interactions
//

import Foundation

/// Errors that can occur during Plaid operations
enum PlaidError: LocalizedError {
    case networkError(Error)
    case serverError(String)
    case invalidResponse
    case noLinkToken
    case exchangeFailed(String)

    var errorDescription: String? {
        switch self {
        case .networkError(let error):
            return "Network error: \(error.localizedDescription)"
        case .serverError(let message):
            return message
        case .invalidResponse:
            return "Invalid response from server"
        case .noLinkToken:
            return "Failed to get link token"
        case .exchangeFailed(let message):
            return "Token exchange failed: \(message)"
        }
    }
}

/// Actor-isolated service for Plaid API calls
actor PlaidService {
    static let shared = PlaidService()

    /// For physical devices, change to your Mac's IP address
    private let baseURL = AppConfig.baseURL

    private init() {}

    // MARK: - Link Token

    /// Create a link token to initialize Plaid Link
    func createLinkToken(userId: String) async throws -> PlaidLinkTokenResponse {
        let url = baseURL.appendingPathComponent("plaid/link-token")
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let body = ["userId": userId]
        request.httpBody = try JSONSerialization.data(withJSONObject: body)

        let (data, response) = try await URLSession.shared.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse else {
            throw PlaidError.invalidResponse
        }

        if httpResponse.statusCode == 200 {
            return try JSONDecoder().decode(PlaidLinkTokenResponse.self, from: data)
        } else {
            if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
               let error = json["error"] as? String {
                throw PlaidError.serverError(error)
            }
            throw PlaidError.noLinkToken
        }
    }

    // MARK: - Token Exchange

    /// Exchange a public token for an access token and fetch initial data
    func exchangePublicToken(
        userId: String,
        publicToken: String,
        institutionId: String?,
        institutionName: String?
    ) async throws -> PlaidExchangeResponse {
        let url = baseURL.appendingPathComponent("plaid/exchange-token")
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        var body: [String: Any] = [
            "userId": userId,
            "publicToken": publicToken
        ]
        if let institutionId = institutionId {
            body["institutionId"] = institutionId
        }
        if let institutionName = institutionName {
            body["institutionName"] = institutionName
        }

        request.httpBody = try JSONSerialization.data(withJSONObject: body)

        let (data, response) = try await URLSession.shared.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse else {
            throw PlaidError.invalidResponse
        }

        if httpResponse.statusCode == 200 {
            return try JSONDecoder().decode(PlaidExchangeResponse.self, from: data)
        } else {
            if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
               let error = json["error"] as? String {
                throw PlaidError.exchangeFailed(error)
            }
            throw PlaidError.exchangeFailed("Unknown error")
        }
    }

    // MARK: - Accounts

    /// Get all linked accounts for a user
    func getLinkedAccounts(userId: String) async throws -> PlaidAccountsResponse {
        let url = baseURL.appendingPathComponent("plaid/accounts/\(userId)")
        var request = URLRequest(url: url)
        request.httpMethod = "GET"

        let (data, response) = try await URLSession.shared.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse else {
            throw PlaidError.invalidResponse
        }

        if httpResponse.statusCode == 200 {
            return try JSONDecoder().decode(PlaidAccountsResponse.self, from: data)
        } else {
            if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
               let error = json["error"] as? String {
                throw PlaidError.serverError(error)
            }
            throw PlaidError.invalidResponse
        }
    }

    // MARK: - Transactions

    /// Get transactions for a user with optional filtering
    func getTransactions(
        userId: String,
        startDate: Date? = nil,
        endDate: Date? = nil,
        limit: Int = 100,
        offset: Int = 0
    ) async throws -> PlaidTransactionsResponse {
        var components = URLComponents(url: baseURL.appendingPathComponent("plaid/transactions/\(userId)"), resolvingAgainstBaseURL: false)!

        var queryItems: [URLQueryItem] = [
            URLQueryItem(name: "limit", value: String(limit)),
            URLQueryItem(name: "offset", value: String(offset))
        ]

        let dateFormatter = DateFormatter()
        dateFormatter.dateFormat = "yyyy-MM-dd"

        if let startDate = startDate {
            queryItems.append(URLQueryItem(name: "startDate", value: dateFormatter.string(from: startDate)))
        }
        if let endDate = endDate {
            queryItems.append(URLQueryItem(name: "endDate", value: dateFormatter.string(from: endDate)))
        }

        components.queryItems = queryItems

        var request = URLRequest(url: components.url!)
        request.httpMethod = "GET"

        let (data, response) = try await URLSession.shared.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse else {
            throw PlaidError.invalidResponse
        }

        if httpResponse.statusCode == 200 {
            return try JSONDecoder().decode(PlaidTransactionsResponse.self, from: data)
        } else {
            if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
               let error = json["error"] as? String {
                throw PlaidError.serverError(error)
            }
            throw PlaidError.invalidResponse
        }
    }

    // MARK: - Sync

    /// Sync new transactions for a user
    func syncTransactions(userId: String) async throws -> PlaidSyncResponse {
        let url = baseURL.appendingPathComponent("plaid/sync/\(userId)")
        var request = URLRequest(url: url)
        request.httpMethod = "POST"

        let (data, response) = try await URLSession.shared.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse else {
            throw PlaidError.invalidResponse
        }

        if httpResponse.statusCode == 200 {
            return try JSONDecoder().decode(PlaidSyncResponse.self, from: data)
        } else {
            if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
               let error = json["error"] as? String {
                throw PlaidError.serverError(error)
            }
            throw PlaidError.invalidResponse
        }
    }

    // MARK: - Unlink

    /// Unlink a bank account
    func unlinkItem(userId: String, itemId: String) async throws {
        let url = baseURL.appendingPathComponent("plaid/unlink/\(userId)/\(itemId)")
        var request = URLRequest(url: url)
        request.httpMethod = "DELETE"

        let (data, response) = try await URLSession.shared.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse else {
            throw PlaidError.invalidResponse
        }

        if httpResponse.statusCode != 200 {
            if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
               let error = json["error"] as? String {
                throw PlaidError.serverError(error)
            }
            throw PlaidError.invalidResponse
        }
    }
}
