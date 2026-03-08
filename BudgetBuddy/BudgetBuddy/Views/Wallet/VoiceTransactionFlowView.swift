//
//  VoiceTransactionFlowView.swift
//  BudgetBuddy
//
//  Composes recording → confirmation → success as one sheet flow
//

import SwiftUI

struct VoiceTransactionFlowView: View {
    var viewModel: VoiceTransactionViewModel
    let onDismiss: () -> Void

    private var savedCount: Int { viewModel.totalCount }

    var body: some View {
        currentScreen
            .interactiveDismissDisabled(viewModel.state == .saving)
    }

    @ViewBuilder
    private var currentScreen: some View {
        switch viewModel.state {
        case .idle, .recording, .parsing, .error:
            VoiceRecordingSheet(viewModel: viewModel)
                .presentationDetents([.medium])
        case .confirming, .saving:
            TransactionConfirmationView(viewModel: viewModel)
                .presentationDetents([.large])
        case .success:
            VoiceTransactionSuccessView(transactionCount: savedCount) {
                viewModel.reset()
                onDismiss()
            }
            .presentationDetents([.medium])
        }
    }
}
