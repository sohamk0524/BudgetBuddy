//
//  VoiceTransactionViewModel.swift
//  BudgetBuddy
//
//  State machine for the voice-to-transaction flow:
//  idle → recording → parsing → confirming → saving → success
//

import Foundation

@Observable
@MainActor
class VoiceTransactionViewModel {

    // MARK: - State Machine

    enum State: Equatable {
        case idle
        case recording
        case parsing
        case confirming
        case saving
        case success
        case error(String)

        static func == (lhs: State, rhs: State) -> Bool {
            switch (lhs, rhs) {
            case (.idle, .idle), (.recording, .recording), (.parsing, .parsing),
                 (.confirming, .confirming), (.saving, .saving), (.success, .success):
                return true
            case (.error(let a), .error(let b)):
                return a == b
            default:
                return false
            }
        }
    }

    // MARK: - Published State

    var state: State = .idle
    var transaction = VoiceTransaction()
    var transcribedText: String = ""

    // MARK: - Dependencies

    let speechRecognizer = SpeechRecognizer()
    private let apiService = APIService.shared

    // MARK: - Recording

    func startRecording() {
        speechRecognizer.requestAuthorization()

        do {
            try speechRecognizer.startRecording()
            state = .recording
        } catch {
            state = .error("Could not start recording: \(error.localizedDescription)")
        }
    }

    func stopRecording() {
        speechRecognizer.stopRecording()
        transcribedText = speechRecognizer.transcribedText

        if transcribedText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            state = .error("No speech detected. Please try again.")
            return
        }

        state = .parsing
        Task {
            await parseTranscription()
        }
    }

    // MARK: - Parsing

    private func parseTranscription() async {
        do {
            let parsed = try await apiService.parseTransaction(statement: transcribedText)
            applyParsedResponse(parsed)
            state = .confirming
        } catch {
            // On parse failure, still allow manual entry
            print("Parse failed: \(error)")
            state = .confirming
        }
    }

    private func applyParsedResponse(_ parsed: ParsedTransactionResponse) {
        transaction.amount = parsed.amount
        transaction.category = parsed.category
        transaction.store = parsed.store
        transaction.notes = parsed.notes

        if let dateString = parsed.date, !dateString.isEmpty {
            let formatter = ISO8601DateFormatter()
            formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
            if let date = formatter.date(from: dateString) {
                transaction.date = date
            } else {
                // Try without fractional seconds
                formatter.formatOptions = [.withInternetDateTime]
                if let date = formatter.date(from: dateString) {
                    transaction.date = date
                }
            }
        }
    }

    // MARK: - Saving

    func saveTransaction() async {
        guard let userId = AuthManager.shared.authToken else {
            state = .error("Not authenticated")
            return
        }

        guard let amount = transaction.amount, amount > 0 else {
            state = .error("Please enter a valid amount")
            return
        }

        state = .saving

        let formatter = ISO8601DateFormatter()
        let request = SaveTransactionRequest(
            userId: userId,
            amount: amount,
            category: transaction.category ?? "Other",
            store: transaction.store,
            date: formatter.string(from: transaction.date),
            notes: transaction.notes
        )

        do {
            let response = try await apiService.saveManualTransaction(request: request)
            if response.success {
                state = .success
            } else {
                state = .error("Failed to save transaction")
            }
        } catch {
            state = .error("Failed to save: \(error.localizedDescription)")
        }
    }

    // MARK: - Manual Entry

    func startManualEntry() {
        transaction = VoiceTransaction()
        transcribedText = ""
        state = .confirming
    }

    // MARK: - Reset

    func reset() {
        state = .idle
        transaction = VoiceTransaction()
        transcribedText = ""
    }
}
