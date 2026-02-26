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

    func analyzeImage(_ image: UIImage) async {
        capturedImage = image
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
            state = .reviewed
        } catch {
            state = .error("Failed to analyze receipt: \(error.localizedDescription)")
        }
    }

    func confirmAndAttach(date: String) async {
        guard let result = analysisResult,
              let userId = AuthManager.shared.authToken else {
            state = .error("Missing data")
            return
        }

        state = .attaching

        do {
            let response = try await APIService.shared.attachReceipt(userId: userId, result: result, date: date)
            attachResponse = response
            state = .done
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
