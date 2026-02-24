//
//  VoiceRecordingSheet.swift
//  BudgetBuddy
//
//  Recording UI with pulsing mic animation and live transcription
//

import SwiftUI

struct VoiceRecordingSheet: View {
    @Bindable var viewModel: VoiceTransactionViewModel

    var body: some View {
        VStack(spacing: 32) {
            switch viewModel.state {
            case .idle, .recording:
                recordingContent
            case .parsing:
                parsingContent
            case .error(let message):
                errorContent(message: message)
            default:
                EmptyView()
            }
        }
        .padding(24)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color.appBackground)
    }

    // MARK: - Recording Content

    private var recordingContent: some View {
        VStack(spacing: 24) {
            Spacer()

            Text(viewModel.state == .recording ? "Listening..." : "Tap to start recording")
                .font(.roundedHeadline)
                .foregroundStyle(Color.textPrimary)

            PulsingMicView(
                isRecording: viewModel.state == .recording,
                audioLevel: viewModel.speechRecognizer.audioLevel
            )

            // Live transcription
            if !viewModel.speechRecognizer.transcribedText.isEmpty {
                Text(viewModel.speechRecognizer.transcribedText)
                    .font(.roundedBody)
                    .foregroundStyle(Color.textPrimary)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal)
                    .frame(minHeight: 60)
            } else if viewModel.state == .recording {
                Text("Say something like \"I spent $10 on coffee at Starbucks\"")
                    .font(.roundedCaption)
                    .foregroundStyle(Color.textSecondary)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal)
                    .frame(minHeight: 60)
            }

            Spacer()

            // Start / Stop button
            Button {
                if viewModel.state == .recording {
                    viewModel.stopRecording()
                } else {
                    viewModel.startRecording()
                }
            } label: {
                HStack(spacing: 8) {
                    Image(systemName: viewModel.state == .recording ? "stop.fill" : "mic.fill")
                    Text(viewModel.state == .recording ? "Stop Recording" : "Start Recording")
                        .font(.roundedHeadline)
                }
                .foregroundStyle(viewModel.state == .recording ? Color.white : Color.appBackground)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 16)
                .background(viewModel.state == .recording ? Color.danger : Color.accent)
                .clipShape(RoundedRectangle(cornerRadius: 14))
            }
        }
    }

    // MARK: - Parsing Content

    private var parsingContent: some View {
        VStack(spacing: 20) {
            Spacer()

            ProgressView()
                .scaleEffect(1.5)
                .tint(Color.accent)

            Text("Analyzing your transaction...")
                .font(.roundedHeadline)
                .foregroundStyle(Color.textPrimary)

            Text("\"\(viewModel.transcribedText)\"")
                .font(.roundedBody)
                .foregroundStyle(Color.textSecondary)
                .italic()
                .multilineTextAlignment(.center)
                .padding(.horizontal)

            Spacer()
        }
    }

    // MARK: - Error Content

    private func errorContent(message: String) -> some View {
        VStack(spacing: 20) {
            Spacer()

            Image(systemName: "exclamationmark.triangle.fill")
                .font(.system(size: 48))
                .foregroundStyle(Color.danger)

            Text(message)
                .font(.roundedBody)
                .foregroundStyle(Color.textPrimary)
                .multilineTextAlignment(.center)
                .padding(.horizontal)

            Button {
                viewModel.reset()
            } label: {
                Text("Try Again")
                    .font(.roundedHeadline)
                    .foregroundStyle(Color.appBackground)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 16)
                    .background(Color.accent)
                    .clipShape(RoundedRectangle(cornerRadius: 14))
            }

            Spacer()
        }
    }
}

// MARK: - Pulsing Mic View

struct PulsingMicView: View {
    let isRecording: Bool
    let audioLevel: Float

    @State private var isPulsing = false

    var body: some View {
        ZStack {
            // Outer pulse rings
            if isRecording {
                Circle()
                    .fill(Color.accent.opacity(0.1))
                    .frame(width: 160 + CGFloat(audioLevel) * 40,
                           height: 160 + CGFloat(audioLevel) * 40)
                    .animation(.easeInOut(duration: 0.15), value: audioLevel)

                Circle()
                    .fill(Color.accent.opacity(0.15))
                    .frame(width: 130 + CGFloat(audioLevel) * 30,
                           height: 130 + CGFloat(audioLevel) * 30)
                    .animation(.easeInOut(duration: 0.15), value: audioLevel)
            }

            // Main mic circle
            Circle()
                .fill(isRecording ? Color.accent : Color.surface)
                .frame(width: 100, height: 100)
                .shadow(color: isRecording ? Color.accent.opacity(0.3) : .clear, radius: 20)

            Image(systemName: isRecording ? "waveform" : "mic.fill")
                .font(.system(size: 36))
                .foregroundStyle(isRecording ? Color.appBackground : Color.accent)
                .symbolEffect(.variableColor, isActive: isRecording)
        }
        .onAppear {
            if isRecording { isPulsing = true }
        }
        .onChange(of: isRecording) { _, newValue in
            isPulsing = newValue
        }
    }
}
