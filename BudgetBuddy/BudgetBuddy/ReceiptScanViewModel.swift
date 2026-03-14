//
//  ReceiptScanViewModel.swift
//  BudgetBuddy
//
//  ViewModel for receipt scanning and classification flow.
//

import SwiftUI
import UIKit

@Observable @MainActor
class ReceiptScanViewModel {
    enum State: Equatable {
        case idle
        case analyzing
        case reviewed
        case attaching
        case done
        case error(String)

        static func == (lhs: State, rhs: State) -> Bool {
            switch (lhs, rhs) {
            case (.idle, .idle), (.analyzing, .analyzing), (.reviewed, .reviewed),
                 (.attaching, .attaching), (.done, .done): return true
            case (.error(let a), .error(let b)): return a == b
            default: return false
            }
        }
    }

    var state: State = .idle
    var capturedImage: UIImage?
    var analysisResult: ReceiptAnalysisResult?
    var attachResponse: ReceiptAttachResponse?
    /// Set to true when backend analysis returns; loading view observes this to fast-drain remaining steps.
    var analysisIsComplete = false

    func analyzeImage(_ image: UIImage) async {
        capturedImage = image
        analysisIsComplete = false
        state = .analyzing

        guard let userId = AuthManager.shared.authToken else {
            state = .error("Not logged in")
            return
        }

        guard let imageData = image.jpegData(compressionQuality: 0.8) else {
            state = .error("Failed to process image")
            return
        }

        do {
            let result = try await APIService.shared.analyzeReceipt(imageData: imageData, userId: userId)
            analysisResult = result
            analysisIsComplete = true   // signal loading view to fast-drain, then it calls finishAnalysis()
        } catch {
            state = .error("Failed to analyze receipt: \(error.localizedDescription)")
        }
    }

    /// Called by ReceiptLoadingView once all animation steps have completed.
    func finishAnalysis() {
        guard analysisResult != nil else { return }
        state = .reviewed
    }

    func confirmAndAttach(category: String, items: [EditableReceiptItem], date: String, merchant: String) async {
        guard let result = analysisResult,
              let userId = AuthManager.shared.authToken else {
            state = .error("Missing data")
            return
        }

        state = .attaching

        // Build result with user-edited merchant and items
        let finalResult = ReceiptAnalysisResult(
            merchant: merchant,
            date: result.date,
            total: result.total,
            items: items.map { $0.toReceiptLineItem() }
        )

        do {
            let response = try await APIService.shared.attachReceipt(
                userId: userId, result: finalResult, category: category, date: date
            )
            attachResponse = response
            state = .done
            NotificationCenter.default.post(
                name: .transactionAdded,
                object: nil,
                userInfo: response.transaction.map { ["transaction": $0] }
            )
        } catch {
            state = .error("Failed to save receipt: \(error.localizedDescription)")
        }
    }

    func reset() {
        state = .idle
        capturedImage = nil
        analysisResult = nil
        attachResponse = nil
    }
}
