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

        // Simulate a "High Spending" alert scenario
        let spent = 1876.0
        let budget = 2500.0
        let idealPace = 1450.0 // Where spending should be at this point in month

        // Return a response with both text and a burndown chart visual component
        return AssistantResponse(
            textMessage: generateMockResponse(for: text, spent: spent, budget: budget),
            visualPayload: .burndownChart(spent: spent, budget: budget, idealPace: idealPace)
        )
    }

    /// Generates a contextual mock response based on user input
    private func generateMockResponse(for userMessage: String, spent: Double, budget: Double) -> String {
        let lowercased = userMessage.lowercased()
        let remaining = budget - spent
        let overBudget = spent > (budget * 0.7) // 70% threshold for alert

        if overBudget {
            return "⚠️ **High Spending Alert!** You've spent $\(Int(spent)) of your $\(Int(budget)) monthly budget. At this pace, you'll exceed your budget by day 24. Consider reducing discretionary spending by $15/day to stay on track."
        } else if lowercased.contains("afford") || lowercased.contains("spend") {
            return "Based on your current spending velocity, you have $\(Int(remaining)) safe to spend. Your upcoming rent payment of $1,200 is accounted for. Here's your spending trajectory:"
        } else if lowercased.contains("budget") {
            return "I've analyzed your spending patterns. You've used \(Int((spent/budget) * 100))% of your monthly budget. Here's your burndown chart:"
        } else if lowercased.contains("save") || lowercased.contains("saving") {
            return "At your current rate, you'll have $\(Int(remaining)) left at month end. Here's how your spending compares to the ideal pace:"
        } else {
            return "Here's your budget overview. You've spent $\(Int(spent)) of $\(Int(budget)) so far this month. The chart below shows your actual spending vs. the ideal pace:"
        }
    }

    /// Generates mock burndown data points for visualization (legacy support)
    func generateMockBurndownData() -> [BurndownDataPoint] {
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
