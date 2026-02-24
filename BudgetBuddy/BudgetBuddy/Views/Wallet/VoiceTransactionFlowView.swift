//
//  VoiceTransactionFlowView.swift
//  BudgetBuddy
//
//  Composes recording → confirmation → success as one sheet flow
//

import SwiftUI

struct VoiceTransactionFlowView: View {
    @Bindable var viewModel: VoiceTransactionViewModel
    let onDismiss: () -> Void

    var body: some View {
        Group {
            switch viewModel.state {
            case .idle, .recording, .parsing:
                VoiceRecordingSheet(viewModel: viewModel)
                    .presentationDetents([.medium])
            case .error:
                VoiceRecordingSheet(viewModel: viewModel)
                    .presentationDetents([.medium])
            case .confirming, .saving:
                TransactionConfirmationView(viewModel: viewModel)
                    .presentationDetents([.large])
            case .success:
                VoiceTransactionSuccessView {
                    viewModel.reset()
                    onDismiss()
                }
                .presentationDetents([.medium])
            }
        }
        .interactiveDismissDisabled(viewModel.state == .saving)
    }
}
