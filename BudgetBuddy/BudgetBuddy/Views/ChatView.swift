//
//  ChatView.swift
//  BudgetBuddy
//
//  Main chat interface with Pulse Header and Generative Widgets
//

import SwiftUI

struct ChatView: View {
    @State private var viewModel = ChatViewModel()
    @FocusState private var isInputFocused: Bool

    var body: some View {
        ZStack(alignment: .top) {
            // Background
            Color.background
                .ignoresSafeArea()

            VStack(spacing: 0) {
                // Pulse Header (Pinned at top)
                PulseHeaderView(
                    safeToSpend: 124.0,
                    isHealthy: true,
                    status: "On Track"
                )

                // Messages ScrollView
                ScrollViewReader { proxy in
                    ScrollView {
                        LazyVStack(spacing: 16) {
                            ForEach(viewModel.messages) { message in
                                MessageRowView(message: message)
                                    .id(message.id)
                            }

                            // Loading indicator
                            if viewModel.isLoading {
                                LoadingBubbleView()
                                    .id("loading")
                            }
                        }
                        .padding()
                        .padding(.bottom, 80) // Space for input bar
                    }
                    .onChange(of: viewModel.messages.count) { _, _ in
                        scrollToBottom(proxy: proxy)
                    }
                    .onChange(of: viewModel.isLoading) { _, isLoading in
                        if isLoading {
                            scrollToBottom(proxy: proxy)
                        }
                    }
                }

                // Error banner
                if let error = viewModel.errorMessage {
                    ErrorBanner(message: error) {
                        viewModel.clearError()
                    }
                }
            }

            // Input Bar (Bottom overlay with blur)
            VStack {
                Spacer()
                InputBarView(
                    text: $viewModel.inputText,
                    isLoading: viewModel.isLoading,
                    isFocused: $isInputFocused
                ) {
                    Task {
                        await viewModel.sendMessage()
                    }
                }
            }
        }
    }

    private func scrollToBottom(proxy: ScrollViewProxy) {
        withAnimation(.easeOut(duration: 0.3)) {
            if viewModel.isLoading {
                proxy.scrollTo("loading", anchor: .bottom)
            } else if let lastMessage = viewModel.messages.last {
                proxy.scrollTo(lastMessage.id, anchor: .bottom)
            }
        }
    }
}

// MARK: - Message Row View

private struct MessageRowView: View {
    let message: ChatMessage

    var body: some View {
        VStack(alignment: message.type == .user ? .trailing : .leading, spacing: 12) {
            // Message content
            if message.type == .user {
                // User message: Right-aligned, gray bubble
                HStack {
                    Spacer(minLength: 60)
                    Text(message.text)
                        .font(.roundedBody)
                        .foregroundStyle(Color.textPrimary)
                        .padding(.horizontal, 16)
                        .padding(.vertical, 12)
                        .background(Color.surface)
                        .clipShape(RoundedRectangle(cornerRadius: 18))
                }
            } else {
                // AI message: Left-aligned, transparent background (text only)
                HStack {
                    Text(message.text)
                        .font(.roundedBody)
                        .foregroundStyle(Color.textPrimary)
                    Spacer(minLength: 60)
                }
            }

            // Visual widget (if present) - shown immediately after AI text
            if let widget = message.visualPayload {
                GenerativeWidgetView(component: widget)
                    .transition(.opacity.combined(with: .scale(scale: 0.95)))
            }

            // Timestamp
            Text(message.timestamp, style: .time)
                .font(.roundedCaption)
                .foregroundStyle(Color.textSecondary)
        }
        .frame(maxWidth: .infinity, alignment: message.type == .user ? .trailing : .leading)
    }
}

// MARK: - Loading Bubble View

private struct LoadingBubbleView: View {
    @State private var animationPhase = 0.0

    var body: some View {
        HStack {
            HStack(spacing: 6) {
                ForEach(0..<3, id: \.self) { index in
                    Circle()
                        .fill(Color.textSecondary)
                        .frame(width: 8, height: 8)
                        .scaleEffect(animationPhase == Double(index) ? 1.3 : 1.0)
                        .animation(
                            .easeInOut(duration: 0.4)
                                .repeatForever()
                                .delay(Double(index) * 0.15),
                            value: animationPhase
                        )
                }
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 12)
            .background(Color.surface)
            .clipShape(RoundedRectangle(cornerRadius: 18))

            Spacer(minLength: 60)
        }
        .onAppear {
            withAnimation(.easeInOut(duration: 0.4).repeatForever()) {
                animationPhase = 2
            }
        }
    }
}

// MARK: - Error Banner

private struct ErrorBanner: View {
    let message: String
    let onDismiss: () -> Void

    var body: some View {
        HStack {
            Image(systemName: "exclamationmark.triangle.fill")
                .foregroundStyle(Color.danger)
            Text(message)
                .font(.roundedCaption)
                .foregroundStyle(Color.textPrimary)
            Spacer()
            Button(action: onDismiss) {
                Image(systemName: "xmark.circle.fill")
                    .foregroundStyle(Color.textSecondary)
            }
        }
        .padding()
        .background(Color.danger.opacity(0.2))
    }
}

// MARK: - Input Bar View

private struct InputBarView: View {
    @Binding var text: String
    let isLoading: Bool
    var isFocused: FocusState<Bool>.Binding
    let onSend: () -> Void

    var body: some View {
        HStack(spacing: 12) {
            TextField("Ask about your finances...", text: $text, axis: .vertical)
                .textFieldStyle(.plain)
                .font(.roundedBody)
                .foregroundStyle(Color.textPrimary)
                .lineLimit(1...5)
                .focused(isFocused)
                .disabled(isLoading)
                .onSubmit {
                    if !text.isEmpty && !isLoading {
                        onSend()
                    }
                }

            Button(action: onSend) {
                Image(systemName: "arrow.up.circle.fill")
                    .font(.title)
                    .foregroundStyle(canSend ? Color.accent : Color.textSecondary)
            }
            .disabled(!canSend)
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 12)
        .background(
            .ultraThinMaterial
                .opacity(0.9)
        )
        .background(Color.surface.opacity(0.8))
        .overlay(
            Rectangle()
                .frame(height: 1)
                .foregroundStyle(Color.textSecondary.opacity(0.2)),
            alignment: .top
        )
    }

    private var canSend: Bool {
        !text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty && !isLoading
    }
}

// MARK: - Preview

#Preview {
    ChatView()
}
