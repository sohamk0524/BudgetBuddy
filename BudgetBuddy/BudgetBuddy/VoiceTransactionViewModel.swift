//
//  VoiceTransactionViewModel.swift
//  BudgetBuddy
//
//  State machine for the voice-to-transaction flow.
//  Supports multi-transaction parsing: one transaction per merchant,
//  reviewed sequentially with back-navigation and per-transaction discard.
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

    // MARK: - State

    var state: State = .idle
    var pendingTransactions: [VoiceTransaction] = []
    var currentIndex: Int = 0
    /// Parallel array tracking the backend ID of each saved transaction (nil = not yet saved).
    var savedTransactionIds: [Int?] = []
    var transcribedText: String = ""

    // MARK: - Computed helpers

    /// The transaction currently being reviewed/edited.
    var transaction: VoiceTransaction {
        get { pendingTransactions.isEmpty ? VoiceTransaction() : pendingTransactions[currentIndex] }
        set { if !pendingTransactions.isEmpty { pendingTransactions[currentIndex] = newValue } }
    }

    var totalCount: Int { max(pendingTransactions.count, 1) }
    var showCounter: Bool { pendingTransactions.count > 1 }
    var canGoBack: Bool { currentIndex > 0 }
    var isLastTransaction: Bool {
        pendingTransactions.isEmpty || currentIndex == pendingTransactions.count - 1
    }

    // MARK: - Dependencies

    let speechRecognizer = SpeechRecognizer()
    private let apiService = APIService.shared

    // MARK: - Recording

    func startRecording() {
        speechRecognizer.requestAuthorization()
        speechRecognizer.onSilenceDetected = { [weak self] in
            self?.stopRecording()
        }
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
        Task { await parseTranscription() }
    }

    // MARK: - Parsing

    private func parseTranscription() async {
        do {
            let group = try await apiService.parseTransaction(
                statement: transcribedText,
                userId: AuthManager.shared.authToken
            )
            applyParsedGroup(group)
            state = .confirming
        } catch {
            print("Parse failed: \(error)")
            pendingTransactions = [VoiceTransaction()]
            savedTransactionIds = [nil]
            currentIndex = 0
            state = .confirming
        }
    }

    private func applyParsedGroup(_ group: ParsedTransactionGroupResponse) {
        let source = group.transactions.isEmpty
            ? [ParsedTransactionWithItems(amount: nil, category: nil, store: nil, date: nil, notes: nil, items: nil)]
            : group.transactions

        let dateFormatter = DateFormatter()
        dateFormatter.dateFormat = "yyyy-MM-dd"

        pendingTransactions = source.map { parsed in
            var txn = VoiceTransaction()
            txn.amount = parsed.amount
            txn.category = parsed.category?.capitalized
            txn.store = parsed.store
            txn.notes = parsed.notes

            if let dateStr = parsed.date, !dateStr.isEmpty,
               let date = dateFormatter.date(from: dateStr) {
                txn.date = date
            }

            if let items = parsed.items {
                txn.items = items.map {
                    EditableReceiptItem(name: $0.name, price: $0.price, category: $0.classification)
                }
            }

            return txn
        }

        savedTransactionIds = Array(repeating: nil, count: pendingTransactions.count)
        currentIndex = 0
    }

    // MARK: - Saving / Confirming

    func saveTransaction() async {
        guard let userId = AuthManager.shared.authToken else {
            state = .error("Not authenticated")
            return
        }

        let txn = transaction
        guard let amount = txn.amount, amount > 0 else {
            state = .error("Please enter a valid amount")
            return
        }

        state = .saving

        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        let source = transcribedText.isEmpty ? "manual" : "voice"

        let itemDicts: [[String: String]]? = txn.items.isEmpty ? nil : txn.items.map {
            ["name": $0.name, "price": String(format: "%.2f", $0.price), "classification": $0.category]
        }

        let request = SaveTransactionRequest(
            userId: userId,
            amount: amount,
            category: txn.category ?? "Other",
            store: txn.store,
            date: formatter.string(from: txn.date),
            notes: txn.notes,
            source: source,
            receiptItems: itemDicts
        )

        do {
            let response: SaveTransactionResponse
            if let existingId = savedTransactionIds[currentIndex] {
                // Already saved — update it
                response = try await apiService.updateManualTransaction(
                    transactionId: existingId, request: request)
            } else {
                // New save
                response = try await apiService.saveManualTransaction(request: request)
                if let idStr = response.transactionId, let id = Int(idStr) {
                    savedTransactionIds[currentIndex] = id
                }
            }

            if response.success {
                NotificationCenter.default.post(
                    name: .transactionAdded,
                    object: nil,
                    userInfo: response.transaction.map { ["transaction": $0] }
                )
                if isLastTransaction {
                    state = .success
                } else {
                    currentIndex += 1
                    state = .confirming
                }
            } else {
                state = .error("Failed to save transaction")
            }
        } catch {
            state = .error("Failed to save: \(error.localizedDescription)")
        }
    }

    // MARK: - Back navigation

    func goBack() {
        guard canGoBack else { return }
        currentIndex -= 1
        state = .confirming
    }

    // MARK: - Discard current transaction

    func discardCurrentTransaction() async {
        if let savedId = savedTransactionIds[currentIndex] {
            try? await apiService.deleteTransaction(transactionId: savedId)
        }

        pendingTransactions.remove(at: currentIndex)
        savedTransactionIds.remove(at: currentIndex)

        if pendingTransactions.isEmpty {
            reset()
            return
        }

        if currentIndex >= pendingTransactions.count {
            currentIndex = pendingTransactions.count - 1
        }
        state = .confirming
    }

    // MARK: - Manual Entry

    func startManualEntry() {
        pendingTransactions = [VoiceTransaction()]
        savedTransactionIds = [nil]
        currentIndex = 0
        transcribedText = ""
        state = .confirming
    }

    // MARK: - Reset

    func reset() {
        state = .idle
        pendingTransactions = []
        savedTransactionIds = []
        currentIndex = 0
        transcribedText = ""
    }
}
