//
//  ChatViewModel.swift
//  BudgetBuddy
//
//  ViewModel for managing chat state and interactions
//

import Foundation

@Observable
final class ChatViewModel {

    // MARK: - Published State

    var messages: [ChatMessage] = []
    var inputText: String = ""
    var isLoading: Bool = false
    var errorMessage: String?

    // MARK: - Dependencies

    private let mockService = MockService()

    // MARK: - Initialization

    init() {
        // Add a welcome message from the assistant
        let welcomeMessage = ChatMessage(
            type: .assistant,
            text: "Hi! I'm BudgetBuddy, your AI financial copilot. Ask me anything about your finances - like \"Can I afford dinner tonight?\" or \"How's my budget looking?\""
        )
        messages.append(welcomeMessage)
    }

    // MARK: - Actions

    /// Sends the current input text as a message
    @MainActor
    func sendMessage() async {
        let text = inputText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { return }

        // Clear input and error state
        inputText = ""
        errorMessage = nil

        // Add user message
        let userMessage = ChatMessage(type: .user, text: text)
        messages.append(userMessage)

        // Set loading state
        isLoading = true

        do {
            // Call mock service
            let response = try await mockService.sendMessage(text: text)

            // Add assistant response
            let assistantMessage = ChatMessage(
                type: .assistant,
                text: response.textMessage,
                visualPayload: response.visualPayload
            )
            messages.append(assistantMessage)

        } catch {
            errorMessage = "Failed to get response. Please try again."
        }

        isLoading = false
    }

    /// Clears the error message
    func clearError() {
        errorMessage = nil
    }
}
