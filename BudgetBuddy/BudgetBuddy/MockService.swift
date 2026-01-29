//
//  MockService.swift
//  BudgetBuddy
//
//  Mock service to simulate API calls during development
//

import Foundation

actor MockService {

    /// Simulates sending a message to the AI backend
    /// - Parameter text: The user's message
    /// - Returns: A simulated AssistantResponse with text and optional visual component
    func sendMessage(text: String) async throws -> AssistantResponse {
        // Simulate network delay (1 second)
        try await Task.sleep(nanoseconds: 1_000_000_000)

        // Generate mock burndown data for the current month
        let burndownData = generateMockBurndownData()

        // Return a response with both text and a visual component
        return AssistantResponse(
            textMessage: generateMockResponse(for: text),
            visualPayload: .budgetBurndown(data: burndownData)
        )
    }

    /// Generates a contextual mock response based on user input
    private func generateMockResponse(for userMessage: String) -> String {
        let lowercased = userMessage.lowercased()

        if lowercased.contains("afford") || lowercased.contains("spend") {
            return "Based on your current spending velocity, you have $127.50 safe to spend today. Your upcoming rent payment of $1,200 is accounted for. Here's your budget burndown for the month:"
        } else if lowercased.contains("budget") {
            return "I've analyzed your spending patterns. You're currently on track with your monthly budget. Here's a visual breakdown of your remaining budget over time:"
        } else if lowercased.contains("save") || lowercased.contains("saving") {
            return "Great question about savings! At your current rate, you'll save $340 this month. Here's how your budget is projected to burn down:"
        } else {
            return "I've pulled up your financial overview. Your safe-to-spend amount is $127.50 for today. Here's your budget burndown chart showing your projected balance through the end of the month:"
        }
    }

    /// Generates mock burndown data points for visualization
    private func generateMockBurndownData() -> [BurndownDataPoint] {
        let calendar = Calendar.current
        let today = Date()

        // Get the start of the current month
        let components = calendar.dateComponents([.year, .month], from: today)
        guard let startOfMonth = calendar.date(from: components) else {
            return []
        }

        // Generate data points for the month
        var dataPoints: [BurndownDataPoint] = []
        var currentAmount = 2500.0 // Starting budget

        // Get number of days in the month
        guard let range = calendar.range(of: .day, in: .month, for: today) else {
            return []
        }

        for day in 0..<range.count {
            guard let date = calendar.date(byAdding: .day, value: day, to: startOfMonth) else {
                continue
            }

            dataPoints.append(BurndownDataPoint(date: date, amount: currentAmount))

            // Simulate daily spending (varying amounts)
            let dailySpend = Double.random(in: 30...120)
            currentAmount = max(0, currentAmount - dailySpend)
        }

        return dataPoints
    }
}
