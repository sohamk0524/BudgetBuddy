//
//  ChatViewModel.swift
//  BudgetBuddy
//
//  ViewModel for managing chat state and interactions
//

import Foundation

@Observable
final class ChatViewModel {

    // MARK: - Configuration

    /// Set to true to use the real Flask backend, false to use mock data
    private let useRealAPI: Bool = true

    // MARK: - Published State

    var messages: [ChatMessage] = []
    var inputText: String = ""
    var isLoading: Bool = false
    var errorMessage: String?

    // MARK: - Dependencies

    private let mockService = MockService()
    private let apiService = APIService.shared

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
            // Call the appropriate service based on configuration
            let response: AssistantResponse
            if useRealAPI {
                response = try await apiService.sendMessage(text: text)
            } else {
                response = try await mockService.sendMessage(text: text)
            }

            // Add assistant response
            let assistantMessage = ChatMessage(
                type: .assistant,
                text: response.textMessage,
                visualPayload: response.visualPayload
            )
            messages.append(assistantMessage)

        } catch let decodingError as DecodingError {
            errorMessage = "Failed to parse response."
            print("Decoding Error: \(decodingError)")
            if case .keyNotFound(let key, let context) = decodingError {
                print("Missing key: \(key.stringValue) in \(context.debugDescription)")
            } else if case .typeMismatch(let type, let context) = decodingError {
                print("Type mismatch: expected \(type) at \(context.codingPath)")
            }
        } catch {
            errorMessage = "Failed to get response. Please try again."
            print("API Error: \(error)")
        }

        isLoading = false
    }

    /// Clears the error message
    func clearError() {
        errorMessage = nil
    }
}
