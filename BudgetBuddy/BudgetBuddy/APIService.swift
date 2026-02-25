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
    /// For physical devices, change to your Mac's IP address (run: ipconfig getifaddr en0)
    static let shared = APIService()

    // MARK: - Initialization

    init() {
        self.baseURL = AppConfig.baseURL
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

    // MARK: - Spending Plan API

    /// Generates a personalized spending plan
    /// - Parameters:
    ///   - userId: The authenticated user's ID
    ///   - planInput: The data collected from the question flow
    /// - Returns: A SpendingPlanResponse with the generated plan
    func generatePlan(userId: Int, planInput: SpendingPlanInput) async throws -> SpendingPlanResponse {
        let url = baseURL.appendingPathComponent("generate-plan")

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        // Format the date for JSON
        let dateFormatter = ISO8601DateFormatter()

        // Build the deep dive data structure
        var deepDiveData: [String: Any] = [:]

        // Fixed expenses
        var subscriptionsArray: [[String: Any]] = []
        for sub in planInput.fixedExpenses.subscriptions {
            subscriptionsArray.append(["name": sub.name, "amount": sub.amount])
        }
        deepDiveData["fixedExpenses"] = [
            "rent": planInput.fixedExpenses.rent,
            "utilities": planInput.fixedExpenses.utilities,
            "subscriptions": subscriptionsArray
        ]

        // Variable spending
        deepDiveData["variableSpending"] = [
            "groceries": planInput.variableSpending.groceries,
            "transportation": [
                "type": planInput.variableSpending.transportation.type,
                "gas": planInput.variableSpending.transportation.gas,
                "insurance": planInput.variableSpending.transportation.insurance,
                "transitPass": planInput.variableSpending.transportation.transitPass
            ],
            "diningEntertainment": planInput.variableSpending.diningEntertainment
        ]

        // Upcoming events
        var eventsArray: [[String: Any]] = []
        for event in planInput.upcomingEvents {
            eventsArray.append([
                "name": event.name,
                "date": dateFormatter.string(from: event.date),
                "cost": event.cost,
                "saveGradually": event.saveGradually
            ])
        }
        deepDiveData["upcomingEvents"] = eventsArray

        // Savings goals
        var goalsArray: [[String: Any]] = []
        for goal in planInput.savingsGoals {
            goalsArray.append([
                "name": goal.name,
                "target": goal.target,
                "current": goal.current,
                "priority": goal.priority
            ])
        }
        deepDiveData["savingsGoals"] = goalsArray

        // Spending preferences
        deepDiveData["spendingPreferences"] = [
            "spendingStyle": planInput.spendingPreferences.spendingStyle,
            "priorities": planInput.spendingPreferences.priorities,
            "strictness": planInput.spendingPreferences.strictness
        ]

        let body: [String: Any] = [
            "userId": userId,
            "deepDiveData": deepDiveData
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
        return try decoder.decode(SpendingPlanResponse.self, from: data)
    }

    /// Gets the user's most recent spending plan
    /// - Parameter userId: The authenticated user's ID
    /// - Returns: A GetPlanResponse with the plan if it exists
    func getPlan(userId: Int) async throws -> GetPlanResponse {
        let url = baseURL.appendingPathComponent("get-plan/\(userId)")

        let (data, response) = try await URLSession.shared.data(from: url)

        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }

        guard httpResponse.statusCode == 200 else {
            throw APIError.serverError(statusCode: httpResponse.statusCode)
        }

        let decoder = JSONDecoder()
        return try decoder.decode(GetPlanResponse.self, from: data)
    }

    // MARK: - User Profile API

    /// Gets the user's profile including name, email, financial info, and linked accounts
    func getUserProfile(userId: Int) async throws -> UserProfile {
        let url = baseURL.appendingPathComponent("user/profile/\(userId)")

        let (data, response) = try await URLSession.shared.data(from: url)

        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            throw APIError.invalidResponse
        }

        return try JSONDecoder().decode(UserProfile.self, from: data)
    }

    /// Updates the user's profile (partial update)
    func updateUserProfile(userId: Int, update: UserProfileUpdateRequest) async throws {
        let url = baseURL.appendingPathComponent("user/profile/\(userId)")

        var request = URLRequest(url: url)
        request.httpMethod = "PUT"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(update)

        let (_, response) = try await URLSession.shared.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            throw APIError.invalidResponse
        }
    }

    /// Gets top spending categories
    func getTopExpenses(userId: Int, days: Int = 30) async throws -> TopExpensesResponse {
        var urlComponents = URLComponents(url: baseURL.appendingPathComponent("user/top-expenses/\(userId)"), resolvingAgainstBaseURL: false)!
        urlComponents.queryItems = [URLQueryItem(name: "days", value: String(days))]

        guard let url = urlComponents.url else {
            throw APIError.invalidResponse
        }

        let (data, response) = try await URLSession.shared.data(from: url)

        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            throw APIError.invalidResponse
        }

        return try JSONDecoder().decode(TopExpensesResponse.self, from: data)
    }

    /// Gets category preferences
    func getCategoryPreferences(userId: Int) async throws -> CategoryPreferencesResponse {
        let url = baseURL.appendingPathComponent("user/category-preferences/\(userId)")

        let (data, response) = try await URLSession.shared.data(from: url)

        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            throw APIError.invalidResponse
        }

        return try JSONDecoder().decode(CategoryPreferencesResponse.self, from: data)
    }

    /// Updates category preferences
    func updateCategoryPreferences(userId: Int, categories: [String]) async throws {
        let url = baseURL.appendingPathComponent("user/category-preferences/\(userId)")

        var request = URLRequest(url: url)
        request.httpMethod = "PUT"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let body: [String: Any] = ["categories": categories]
        request.httpBody = try JSONSerialization.data(withJSONObject: body)

        let (_, response) = try await URLSession.shared.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            throw APIError.invalidResponse
        }
    }

    // MARK: - Expense Classification API

    /// Gets expenses with sub-category classification data
    func getExpenses(userId: Int, startDate: String? = nil, endDate: String? = nil, category: String? = nil, subCategory: String? = nil, limit: Int = 100, offset: Int = 0) async throws -> ExpensesResponse {
        var urlComponents = URLComponents(url: baseURL.appendingPathComponent("expenses/\(userId)"), resolvingAgainstBaseURL: false)!
        var queryItems = [
            URLQueryItem(name: "limit", value: String(limit)),
            URLQueryItem(name: "offset", value: String(offset))
        ]
        if let startDate { queryItems.append(URLQueryItem(name: "startDate", value: startDate)) }
        if let endDate { queryItems.append(URLQueryItem(name: "endDate", value: endDate)) }
        if let category { queryItems.append(URLQueryItem(name: "category", value: category)) }
        if let subCategory { queryItems.append(URLQueryItem(name: "subCategory", value: subCategory)) }
        urlComponents.queryItems = queryItems

        guard let url = urlComponents.url else { throw APIError.invalidResponse }

        let (data, response) = try await URLSession.shared.data(from: url)
        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
            throw APIError.invalidResponse
        }
        return try JSONDecoder().decode(ExpensesResponse.self, from: data)
    }

    /// Classifies a merchant for a user (retroactive)
    func classifyMerchant(userId: Int, merchantName: String, classification: String, essentialRatio: Double? = nil) async throws -> ClassifyMerchantResponse {
        let url = baseURL.appendingPathComponent("merchant/classify")

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        var body: [String: Any] = [
            "userId": userId,
            "merchantName": merchantName,
            "classification": classification
        ]
        if let essentialRatio { body["essentialRatio"] = essentialRatio }
        request.httpBody = try JSONSerialization.data(withJSONObject: body)

        let (data, response) = try await URLSession.shared.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
            throw APIError.invalidResponse
        }
        return try JSONDecoder().decode(ClassifyMerchantResponse.self, from: data)
    }

    /// Classifies a single transaction
    func classifyTransaction(transactionId: Int, subCategory: String, essentialRatio: Double? = nil) async throws -> ClassifyTransactionResponse {
        let url = baseURL.appendingPathComponent("transaction/\(transactionId)/classify")

        var request = URLRequest(url: url)
        request.httpMethod = "PUT"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        var body: [String: Any] = ["subCategory": subCategory]
        if let essentialRatio { body["essentialRatio"] = essentialRatio }
        request.httpBody = try JSONSerialization.data(withJSONObject: body)

        let (data, response) = try await URLSession.shared.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
            throw APIError.invalidResponse
        }
        return try JSONDecoder().decode(ClassifyTransactionResponse.self, from: data)
    }

    /// Gets all merchant classifications for a user
    func getMerchantClassifications(userId: Int) async throws -> MerchantClassificationsResponse {
        let url = baseURL.appendingPathComponent("merchant/classifications/\(userId)")

        let (data, response) = try await URLSession.shared.data(from: url)
        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
            throw APIError.invalidResponse
        }
        return try JSONDecoder().decode(MerchantClassificationsResponse.self, from: data)
    }

    /// Gets unclassified transactions sorted by merchant impact (round-robin)
    func getUnclassifiedTransactions(userId: Int, limit: Int = 10) async throws -> UnclassifiedTransactionsResponse {
        var urlComponents = URLComponents(url: baseURL.appendingPathComponent("expenses/unclassified/\(userId)"), resolvingAgainstBaseURL: false)!
        urlComponents.queryItems = [URLQueryItem(name: "limit", value: String(limit))]

        guard let url = urlComponents.url else { throw APIError.invalidResponse }

        let (data, response) = try await URLSession.shared.data(from: url)
        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
            throw APIError.invalidResponse
        }
        return try JSONDecoder().decode(UnclassifiedTransactionsResponse.self, from: data)
    }

    // MARK: - Device Token API

    /// Registers a device token for push notifications
    func registerDeviceToken(userId: Int, token: String) async throws {
        let url = baseURL.appendingPathComponent("device/register")

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let body: [String: Any] = [
            "userId": userId,
            "token": token,
            "platform": "ios"
        ]
        request.httpBody = try JSONSerialization.data(withJSONObject: body)

        let (_, response) = try await URLSession.shared.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
            throw APIError.invalidResponse
        }
    }

    /// Unregisters a device token (e.g., on logout)
    func unregisterDeviceToken(userId: Int, token: String) async throws {
        let url = baseURL.appendingPathComponent("device/unregister")

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let body: [String: Any] = [
            "userId": userId,
            "token": token
        ]
        request.httpBody = try JSONSerialization.data(withJSONObject: body)

        let (_, response) = try await URLSession.shared.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
            throw APIError.invalidResponse
        }
    }

    /// Triggers LLM-based batch auto-classification for unclassified merchants
    func autoClassifyMerchants(userId: Int) async throws -> AutoClassifyResponse {
        let url = baseURL.appendingPathComponent("expenses/auto-classify/\(userId)")

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let (data, response) = try await URLSession.shared.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
            throw APIError.invalidResponse
        }
        return try JSONDecoder().decode(AutoClassifyResponse.self, from: data)
    }

    /// Gets smart nudges
    func getNudges(userId: Int) async throws -> NudgesResponse {
        let url = baseURL.appendingPathComponent("user/nudges/\(userId)")

        let (data, response) = try await URLSession.shared.data(from: url)

        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            throw APIError.invalidResponse
        }

        return try JSONDecoder().decode(NudgesResponse.self, from: data)
    }

    /// Gets cached or fresh recommendations
    func getRecommendations(userId: Int) async throws -> RecommendationsResponse {
        let url = baseURL.appendingPathComponent("recommendations/\(userId)")

        let (data, response) = try await URLSession.shared.data(from: url)

        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            throw APIError.invalidResponse
        }

        return try JSONDecoder().decode(RecommendationsResponse.self, from: data)
    }

    /// Force-generates fresh recommendations
    func generateRecommendations(userId: Int, action: String = "general") async throws -> RecommendationsResponse {
        let url = baseURL.appendingPathComponent("recommendations/generate")

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let body: [String: Any] = [
            "userId": userId,
            "action": action
        ]
        request.httpBody = try JSONSerialization.data(withJSONObject: body)

        let (data, response) = try await URLSession.shared.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            throw APIError.invalidResponse
        }

        return try JSONDecoder().decode(RecommendationsResponse.self, from: data)
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
