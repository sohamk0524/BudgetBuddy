//
//  SpendingPlanViewModel.swift
//  BudgetBuddy
//
//  ViewModel for the spending plan question flow and plan display
//

import SwiftUI
import Observation

@Observable
final class SpendingPlanViewModel {
    // MARK: - Question Flow State
    var currentQuestionIndex: Int = 0
    var planInput: SpendingPlanInput = SpendingPlanInput()

    // MARK: - Plan State
    var currentPlan: SpendingPlan?
    var hasPlan: Bool = false

    // MARK: - UI State
    var isLoading: Bool = false
    var isGenerating: Bool = false
    var errorMessage: String?
    var showQuestionFlow: Bool = false

    // MARK: - Questions Configuration

    struct Question {
        let id: String
        let category: String
        let title: String
        let subtitle: String
        let type: QuestionType

        enum QuestionType {
            case currency(keyPath: WritableKeyPath<SpendingPlanInput, Double>)
            case picker(options: [(String, String)], keyPath: WritableKeyPath<SpendingPlanInput, String>)
            case slider(range: ClosedRange<Double>, keyPath: WritableKeyPath<SpendingPlanInput, Double>)
            case subscriptions
            case upcomingEvents
            case savingsGoals
            case transportationType
            case multiSelect(options: [(String, String)])
        }
    }

    var questions: [Question] {
        var qs: [Question] = []

        // Fixed Expenses
        qs.append(Question(
            id: "rent",
            category: "Fixed Expenses",
            title: "Monthly Rent or Mortgage",
            subtitle: "Your housing payment each month",
            type: .currency(keyPath: \.fixedExpenses.rent)
        ))

        qs.append(Question(
            id: "utilities",
            category: "Fixed Expenses",
            title: "Monthly Utilities",
            subtitle: "Electric, water, internet, etc.",
            type: .currency(keyPath: \.fixedExpenses.utilities)
        ))

        qs.append(Question(
            id: "subscriptions",
            category: "Fixed Expenses",
            title: "Subscription Services",
            subtitle: "Netflix, Spotify, gym, etc.",
            type: .subscriptions
        ))

        // Variable Spending
        qs.append(Question(
            id: "groceries",
            category: "Variable Spending",
            title: "Monthly Groceries",
            subtitle: "Food and household essentials",
            type: .currency(keyPath: \.variableSpending.groceries)
        ))

        qs.append(Question(
            id: "transportation",
            category: "Variable Spending",
            title: "Transportation",
            subtitle: "How do you get around?",
            type: .transportationType
        ))

        qs.append(Question(
            id: "dining",
            category: "Variable Spending",
            title: "Dining & Entertainment",
            subtitle: "Restaurants, movies, activities",
            type: .currency(keyPath: \.variableSpending.diningEntertainment)
        ))

        // Upcoming Events
        qs.append(Question(
            id: "events",
            category: "Upcoming Events",
            title: "Big Expenses Coming Up?",
            subtitle: "Trips, gifts, large purchases in the next 3 months",
            type: .upcomingEvents
        ))

        // Savings Goals
        qs.append(Question(
            id: "goals",
            category: "Savings Goals",
            title: "What Are You Saving For?",
            subtitle: "Add your savings targets",
            type: .savingsGoals
        ))

        // Preferences
        qs.append(Question(
            id: "style",
            category: "Preferences",
            title: "Spending Style",
            subtitle: "How would you describe your approach?",
            type: .slider(range: 0...1, keyPath: \.spendingPreferences.spendingStyle)
        ))

        qs.append(Question(
            id: "strictness",
            category: "Preferences",
            title: "Budget Strictness",
            subtitle: "How strict should your plan be?",
            type: .picker(options: [
                ("flexible", "Flexible - Guidelines, not rules"),
                ("moderate", "Moderate - Some wiggle room"),
                ("strict", "Strict - Keep me accountable")
            ], keyPath: \.spendingPreferences.strictness)
        ))

        return qs
    }

    var totalQuestions: Int { questions.count }

    var currentQuestion: Question? {
        guard currentQuestionIndex < questions.count else { return nil }
        return questions[currentQuestionIndex]
    }

    var progress: Double {
        guard totalQuestions > 0 else { return 0 }
        return Double(currentQuestionIndex) / Double(totalQuestions)
    }

    var canGoBack: Bool { currentQuestionIndex > 0 }
    var canGoNext: Bool { currentQuestionIndex < totalQuestions - 1 }
    var isLastQuestion: Bool { currentQuestionIndex == totalQuestions - 1 }

    // MARK: - Navigation

    func nextQuestion() {
        if currentQuestionIndex < totalQuestions - 1 {
            currentQuestionIndex += 1
        }
    }

    func previousQuestion() {
        if currentQuestionIndex > 0 {
            currentQuestionIndex -= 1
        }
    }

    func startQuestionFlow() {
        currentQuestionIndex = 0
        planInput = SpendingPlanInput()
        showQuestionFlow = true
    }

    func cancelQuestionFlow() {
        showQuestionFlow = false
        currentQuestionIndex = 0
    }

    // MARK: - API Calls

    @MainActor
    func loadExistingPlan() async {
        guard let userId = AuthManager.shared.authToken else { return }

        isLoading = true
        errorMessage = nil

        do {
            let response = try await APIService.shared.getPlan(userId: userId)
            hasPlan = response.hasPlan
            currentPlan = response.plan
        } catch {
            errorMessage = error.localizedDescription
        }

        isLoading = false
    }

    @MainActor
    func generatePlan() async {
        guard let userId = AuthManager.shared.authToken else { return }

        isGenerating = true
        errorMessage = nil

        do {
            let response = try await APIService.shared.generatePlan(userId: userId, planInput: planInput)
            // Update state in a single batch to ensure UI refresh
            let plan = response.plan
            currentPlan = plan
            hasPlan = plan != nil
            isGenerating = false
            // Dismiss the question flow after state is updated
            showQuestionFlow = false
        } catch {
            errorMessage = "Failed to generate plan: \(error.localizedDescription)"
            isGenerating = false
        }
    }

    // MARK: - Helpers

    func addSubscription() {
        planInput.fixedExpenses.subscriptions.append(Subscription())
    }

    func removeSubscription(at index: Int) {
        guard index < planInput.fixedExpenses.subscriptions.count else { return }
        planInput.fixedExpenses.subscriptions.remove(at: index)
    }

    func addUpcomingEvent() {
        planInput.upcomingEvents.append(UpcomingEvent())
    }

    func removeUpcomingEvent(at index: Int) {
        guard index < planInput.upcomingEvents.count else { return }
        planInput.upcomingEvents.remove(at: index)
    }

    func addSavingsGoal() {
        let priority = planInput.savingsGoals.count + 1
        planInput.savingsGoals.append(SavingsGoal(priority: priority))
    }

    func removeSavingsGoal(at index: Int) {
        guard index < planInput.savingsGoals.count else { return }
        planInput.savingsGoals.remove(at: index)
    }
}
