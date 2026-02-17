//
//  ChatView.swift
//  BudgetBuddy
//
//  Main chat interface with Pulse Header and Generative Widgets
//

import SwiftUI
import UniformTypeIdentifiers

struct ChatView: View {
    @State private var viewModel = ChatViewModel()
    @FocusState private var isInputFocused: Bool
    @State private var showingFilePicker = false
    @State private var isTypingMode = false
    @State private var showingSubMenu: QuickActionSubMenu?

    var body: some View {
        ZStack(alignment: .top) {
            // Background
            Color.appBackground
                .ignoresSafeArea()

            VStack(spacing: 0) {
                // Pulse Header (Pinned at top) - uses live data from viewModel
                PulseHeaderView(
                    safeToSpend: viewModel.safeToSpend,
                    isHealthy: viewModel.safeToSpend > 100,
                    status: pulseStatus
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
                        .padding(.bottom, 160) // Space for quick-action grid
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

            // Input Area (Bottom overlay)
            VStack {
                Spacer()
                if isTypingMode {
                    InputBarView(
                        text: $viewModel.inputText,
                        isLoading: viewModel.isLoading,
                        isFocused: $isInputFocused,
                        onAttach: { showingFilePicker = true },
                        onDismiss: {
                            isTypingMode = false
                            isInputFocused = false
                        }
                    ) {
                        Task {
                            await viewModel.sendMessage()
                        }
                    }
                } else {
                    QuickActionGridView(isLoading: viewModel.isLoading) { action in
                        handleQuickAction(action)
                    }
                }
            }
        }
        .sheet(item: $showingSubMenu) { menu in
            QuickActionSubMenuView(
                menu: menu,
                onSendPrompt: { prompt in
                    showingSubMenu = nil
                    sendQuickPrompt(prompt)
                },
                onPrefillType: { prefill in
                    showingSubMenu = nil
                    viewModel.inputText = prefill
                    isTypingMode = true
                    DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) {
                        isInputFocused = true
                    }
                }
            )
        }
        .fileImporter(
            isPresented: $showingFilePicker,
            allowedContentTypes: [.pdf, .commaSeparatedText],
            allowsMultipleSelection: false
        ) { result in
            switch result {
            case .success(let urls):
                if let url = urls.first {
                    Task {
                        await viewModel.uploadStatement(url: url)
                    }
                }
            case .failure(let error):
                viewModel.errorMessage = "Failed to select file: \(error.localizedDescription)"
            }
        }
        .task {
            // Fetch financial summary on appear
            await viewModel.fetchFinancialSummary()
        }
    }

    /// Computed status for the Pulse Header
    private var pulseStatus: String {
        if !viewModel.hasData {
            return "No Data"
        } else if viewModel.safeToSpend > 500 {
            return "Looking Good"
        } else if viewModel.safeToSpend > 100 {
            return "On Track"
        } else if viewModel.safeToSpend > 0 {
            return "Be Careful"
        } else {
            return "Over Budget"
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

    private func handleQuickAction(_ action: QuickActionOption) {
        switch action {
        case .craving:
            showingSubMenu = .craving
        case .goTo:
            showingSubMenu = .goTo
        case .onTrack:
            sendQuickPrompt("Am I on track?")
        case .justSpent:
            showingSubMenu = .justSpent
        case .canAfford:
            showingSubMenu = .canAfford
        case .typeOwn:
            isTypingMode = true
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.1) {
                isInputFocused = true
            }
        }
    }

    private func sendQuickPrompt(_ prompt: String) {
        viewModel.inputText = prompt
        Task {
            await viewModel.sendMessage()
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
                // AI message: Left-aligned, markdown rendered
                HStack {
                    MarkdownTextView(text: message.text)
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

// MARK: - Markdown Text View

private struct MarkdownTextView: View {
    let text: String

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            ForEach(Array(parseBlocks().enumerated()), id: \.offset) { _, block in
                switch block {
                case .heading(let level, let content):
                    markdownInline(content)
                        .font(headingFont(level))
                        .foregroundStyle(Color.textPrimary)
                case .paragraph(let content):
                    markdownInline(content)
                        .font(.roundedBody)
                        .foregroundStyle(Color.textPrimary)
                case .listItem(let content):
                    HStack(alignment: .top, spacing: 6) {
                        Text("\u{2022}")
                            .font(.roundedBody)
                            .foregroundStyle(Color.accent)
                        markdownInline(content)
                            .font(.roundedBody)
                            .foregroundStyle(Color.textPrimary)
                    }
                case .numberedItem(let number, let content):
                    HStack(alignment: .top, spacing: 6) {
                        Text("\(number).")
                            .font(.roundedBody)
                            .foregroundStyle(Color.accent)
                            .frame(minWidth: 20, alignment: .trailing)
                        markdownInline(content)
                            .font(.roundedBody)
                            .foregroundStyle(Color.textPrimary)
                    }
                case .codeBlock(let content):
                    Text(content)
                        .font(.system(.caption, design: .monospaced))
                        .foregroundStyle(Color.textPrimary)
                        .padding(10)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .background(Color.surface)
                        .clipShape(RoundedRectangle(cornerRadius: 8))
                case .divider:
                    Rectangle()
                        .fill(Color.textSecondary.opacity(0.3))
                        .frame(height: 1)
                }
            }
        }
    }

    private func markdownInline(_ text: String) -> Text {
        if let attributed = try? AttributedString(markdown: text, options: .init(interpretedSyntax: .inlineOnlyPreservingWhitespace)) {
            return Text(attributed)
        }
        return Text(text)
    }

    private func headingFont(_ level: Int) -> Font {
        switch level {
        case 1: return .system(.title2, design: .rounded, weight: .bold)
        case 2: return .system(.headline, design: .rounded, weight: .bold)
        default: return .system(.subheadline, design: .rounded, weight: .semibold)
        }
    }

    // MARK: - Block-level markdown parser

    private enum MarkdownBlock {
        case heading(level: Int, content: String)
        case paragraph(content: String)
        case listItem(content: String)
        case numberedItem(number: Int, content: String)
        case codeBlock(content: String)
        case divider
    }

    private func parseBlocks() -> [MarkdownBlock] {
        var blocks: [MarkdownBlock] = []
        let lines = text.components(separatedBy: "\n")
        var inCodeBlock = false
        var codeLines: [String] = []
        var paragraphLines: [String] = []

        func flushParagraph() {
            let joined = paragraphLines.joined(separator: " ").trimmingCharacters(in: .whitespaces)
            if !joined.isEmpty {
                blocks.append(.paragraph(content: joined))
            }
            paragraphLines.removeAll()
        }

        for line in lines {
            let trimmed = line.trimmingCharacters(in: .whitespaces)

            // Code fence
            if trimmed.hasPrefix("```") {
                if inCodeBlock {
                    blocks.append(.codeBlock(content: codeLines.joined(separator: "\n")))
                    codeLines.removeAll()
                    inCodeBlock = false
                } else {
                    flushParagraph()
                    inCodeBlock = true
                }
                continue
            }

            if inCodeBlock {
                codeLines.append(line)
                continue
            }

            // Empty line = paragraph break
            if trimmed.isEmpty {
                flushParagraph()
                continue
            }

            // Divider
            if trimmed.allSatisfy({ $0 == "-" || $0 == "*" || $0 == "_" }) && trimmed.count >= 3 {
                flushParagraph()
                blocks.append(.divider)
                continue
            }

            // Heading (e.g. "## Title")
            if trimmed.hasPrefix("#") {
                let hashes = trimmed.prefix(while: { $0 == "#" })
                let level = min(hashes.count, 3)
                let rest = trimmed.dropFirst(level).trimmingCharacters(in: .whitespaces)
                if !rest.isEmpty {
                    flushParagraph()
                    blocks.append(.heading(level: level, content: rest))
                    continue
                }
            }

            // Unordered list item (e.g. "- item" or "* item")
            if (trimmed.hasPrefix("- ") || trimmed.hasPrefix("* ") || trimmed.hasPrefix("+ ")) && trimmed.count > 2 {
                flushParagraph()
                let content = String(trimmed.dropFirst(2))
                blocks.append(.listItem(content: content))
                continue
            }

            // Numbered list item (e.g. "1. item" or "1) item")
            if let dotIndex = trimmed.firstIndex(where: { $0 == "." || $0 == ")" }),
               let num = Int(trimmed[trimmed.startIndex..<dotIndex]),
               trimmed.index(after: dotIndex) < trimmed.endIndex,
               trimmed[trimmed.index(after: dotIndex)] == " " {
                flushParagraph()
                let content = String(trimmed[trimmed.index(dotIndex, offsetBy: 2)...])
                blocks.append(.numberedItem(number: num, content: content))
                continue
            }

            // Regular text line — accumulate into paragraph
            paragraphLines.append(trimmed)
        }

        // Flush remaining
        if inCodeBlock && !codeLines.isEmpty {
            blocks.append(.codeBlock(content: codeLines.joined(separator: "\n")))
        }
        flushParagraph()

        return blocks
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
    let onAttach: () -> Void
    let onDismiss: () -> Void
    let onSend: () -> Void

    var body: some View {
        HStack(spacing: 12) {
            // Close typing mode button
            Button(action: onDismiss) {
                Image(systemName: "xmark.circle.fill")
                    .font(.title2)
                    .foregroundStyle(Color.textSecondary)
            }

            // Attachment button
            Button(action: onAttach) {
                Image(systemName: "paperclip")
                    .font(.title2)
                    .foregroundStyle(isLoading ? Color.textSecondary : Color.accent)
            }
            .disabled(isLoading)

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

// MARK: - Quick Action Grid View (Primary input - always visible)

private struct QuickActionGridView: View {
    let isLoading: Bool
    let onAction: (QuickActionOption) -> Void

    var body: some View {
        VStack(spacing: 0) {
            // Divider
            Rectangle()
                .frame(height: 1)
                .foregroundStyle(Color.textSecondary.opacity(0.2))

            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible()), GridItem(.flexible())], spacing: 10) {
                ForEach(QuickActionOption.allCases) { option in
                    Button {
                        onAction(option)
                    } label: {
                        VStack(spacing: 6) {
                            Image(systemName: option.icon)
                                .font(.title3)
                            Text(option.rawValue)
                                .font(.system(.caption2, design: .rounded))
                                .multilineTextAlignment(.center)
                                .lineLimit(2)
                        }
                        .frame(maxWidth: .infinity, minHeight: 60)
                        .foregroundStyle(Color.textPrimary)
                        .background(Color.surface)
                        .clipShape(RoundedRectangle(cornerRadius: 12))
                    }
                    .disabled(isLoading)
                }
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 10)
        }
        .background(Color.appBackground)
    }
}

// MARK: - Preview

#Preview {
    ChatView()
}
