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
    static let shared = APIService(host: "127.0.0.1", port: 5000)

    // MARK: - Initialization

    init(host: String, port: Int) {
        self.baseURL = URL(string: "http://\(host):\(port)")!
    }

    // MARK: - Chat API

    /// Sends a message to the AI backend and returns the response
    /// - Parameters:
    ///   - text: The user's message
    ///   - userId: The authenticated user's ID (from AuthManager.authToken)
    /// - Returns: An AssistantResponse with text and optional visual component
    func sendMessage(text: String, userId: Int?) async throws -> AssistantResponse {
        let url = baseURL.appendingPathComponent("chat")

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let body: [String: Any] = [
            "message": text,
            "userId": userId ?? "anonymous"
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

    // MARK: - Statement Upload API

    /// Uploads a bank statement file for analysis
    /// - Parameters:
    ///   - fileURL: Local URL to the PDF or CSV file
    ///   - userId: The authenticated user's ID (statement will be saved if provided)
    /// - Returns: An AssistantResponse with analysis and optional visual component
    func uploadStatement(fileURL: URL, userId: Int?) async throws -> AssistantResponse {
        let url = baseURL.appendingPathComponent("upload-statement")

        // Read file data
        let fileData = try Data(contentsOf: fileURL)
        let filename = fileURL.lastPathComponent

        // Build multipart form data
        let boundary = UUID().uuidString
        var body = Data()

        // Add file field
        body.append("--\(boundary)\r\n".data(using: .utf8)!)
        body.append("Content-Disposition: form-data; name=\"file\"; filename=\"\(filename)\"\r\n".data(using: .utf8)!)
        body.append("Content-Type: application/octet-stream\r\n\r\n".data(using: .utf8)!)
        body.append(fileData)
        body.append("\r\n".data(using: .utf8)!)

        // Add userId field if authenticated
        if let userId = userId {
            body.append("--\(boundary)\r\n".data(using: .utf8)!)
            body.append("Content-Disposition: form-data; name=\"userId\"\r\n\r\n".data(using: .utf8)!)
            body.append("\(userId)\r\n".data(using: .utf8)!)
        }

        body.append("--\(boundary)--\r\n".data(using: .utf8)!)

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
        request.httpBody = body

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

    // MARK: - Financial Summary API

    /// Gets the financial summary derived from the user's saved statement
    /// - Parameter userId: The authenticated user's ID
    /// - Returns: A FinancialSummary with net worth, safe to spend, and statement info
    func getFinancialSummary(userId: Int) async throws -> FinancialSummary {
        var urlComponents = URLComponents(url: baseURL.appendingPathComponent("user/financial-summary"), resolvingAgainstBaseURL: false)!
        urlComponents.queryItems = [URLQueryItem(name: "userId", value: String(userId))]

        guard let url = urlComponents.url else {
            throw APIError.invalidResponse
        }

        let (data, response) = try await URLSession.shared.data(from: url)

        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }

        guard httpResponse.statusCode == 200 else {
            throw APIError.serverError(statusCode: httpResponse.statusCode)
        }

        let decoder = JSONDecoder()
        return try decoder.decode(FinancialSummary.self, from: data)
    }

    /// Deletes the user's saved statement
    /// - Parameter userId: The authenticated user's ID
    func deleteStatement(userId: Int) async throws {
        var urlComponents = URLComponents(url: baseURL.appendingPathComponent("user/statement"), resolvingAgainstBaseURL: false)!
        urlComponents.queryItems = [URLQueryItem(name: "userId", value: String(userId))]

        guard let url = urlComponents.url else {
            throw APIError.invalidResponse
        }

        var request = URLRequest(url: url)
        request.httpMethod = "DELETE"

        let (_, response) = try await URLSession.shared.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }

        guard httpResponse.statusCode == 204 else {
            throw APIError.serverError(statusCode: httpResponse.statusCode)
        }
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
