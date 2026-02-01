//
//  APIService.swift
//  BudgetBuddy
//
//  Service for communicating with the Flask backend API
//

import Foundation

actor APIService {

    // MARK: - Configuration

    /// The base URL for the Flask backend
    /// Use localhost for iOS Simulator, or your machine's IP for physical devices
    private let baseURL: URL

    /// Shared instance using localhost (for simulator)
    static let shared = APIService(host: "localhost", port: 5000)

    // MARK: - Initialization

    init(host: String, port: Int) {
        self.baseURL = URL(string: "http://\(host):\(port)")!
    }

    // MARK: - Chat API

    /// Sends a message to the AI backend and returns the response
    /// - Parameters:
    ///   - text: The user's message
    ///   - userId: The user's identifier
    /// - Returns: An AssistantResponse with text and optional visual component
    func sendMessage(text: String, userId: String = "user123") async throws -> AssistantResponse {
        let url = baseURL.appendingPathComponent("chat")

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let body: [String: Any] = [
            "message": text,
            "userId": userId
        ]

        request.httpBody = try JSONSerialization.data(withJSONObject: body)

        let (data, response) = try await URLSession.shared.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }

        guard httpResponse.statusCode == 200 else {
            throw APIError.serverError(statusCode: httpResponse.statusCode)
        }

        let decoder = JSONDecoder()
        return try decoder.decode(AssistantResponse.self, from: data)
    }

    /// Checks if the backend is available
    func healthCheck() async -> Bool {
        let url = baseURL.appendingPathComponent("health")

        do {
            let (data, response) = try await URLSession.shared.data(from: url)
            guard let httpResponse = response as? HTTPURLResponse,
                  httpResponse.statusCode == 200 else {
                return false
            }

            if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
               let status = json["status"] as? String {
                return status == "ok"
            }
            return false
        } catch {
            return false
        }
    }
}

// MARK: - Errors

enum APIError: LocalizedError {
    case invalidResponse
    case serverError(statusCode: Int)
    case decodingError(Error)

    var errorDescription: String? {
        switch self {
        case .invalidResponse:
            return "Invalid response from server"
        case .serverError(let statusCode):
            return "Server error: \(statusCode)"
        case .decodingError(let error):
            return "Failed to decode response: \(error.localizedDescription)"
        }
    }
}
