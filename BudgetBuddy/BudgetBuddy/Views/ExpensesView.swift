//
//  ExpensesView.swift
//  BudgetBuddy
//
//  Expenses tab with smart sub-categorization and swipe-to-classify
//

import SwiftUI

struct ExpensesView: View {
    @Bindable var viewModel: ExpensesViewModel
    @State private var showVoiceRecording = false
    @State private var voiceViewModel = VoiceTransactionViewModel()
    @State private var showReceiptScan = false
    @State private var receiptViewModel = ReceiptScanViewModel()

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                ScrollView {
                    VStack(spacing: 16) {
                        ExpensesSummaryCard(summary: viewModel.summary)

                        // Filter picker
                        Picker("Filter", selection: $viewModel.selectedFilter) {
                            ForEach(ExpenseFilter.allCases, id: \.self) { filter in
                                Text(filter.rawValue).tag(filter)
                            }
                        }
                        .pickerStyle(.segmented)
                        .padding(.horizontal)
                        .onChange(of: viewModel.selectedFilter) {
                            Task { await viewModel.fetchExpenses() }
                        }

                        // Swipe classification card
                        if viewModel.currentClassifyIndex < viewModel.unclassifiedTransactions.count {
                            let txn = viewModel.unclassifiedTransactions[viewModel.currentClassifyIndex]
                            SwipeClassificationCard(
                                transaction: txn,
                                remainingCount: viewModel.totalUnclassifiedCount
                            ) { classification, ratio in
                                Task {
                                    await viewModel.classifyViaSwipe(
                                        transactionId: txn.id,
                                        classification: classification,
                                        essentialRatio: ratio
                                    )
                                }
                            } onSplitRequest: {
                                viewModel.splitTransaction = txn
                                viewModel.showSplitSheet = true
                            }

                            // Auto-classify button when enough unclassified
                            if viewModel.totalUnclassifiedCount > 5 {
                                Button {
                                    Task { await viewModel.autoClassifyWithAI() }
                                } label: {
                                    HStack(spacing: 8) {
                                        if viewModel.isAutoClassifying {
                                            ProgressView()
                                                .tint(.white)
                                        // } else {
                                        //     Image(systemName: "sparkles")
                                        }
                                        Text(viewModel.isAutoClassifying ? "Classifying..." : "Auto-Classify All")
                                            .font(.roundedBody)
                                            .fontWeight(.medium)
                                    }
                                    .foregroundStyle(.white)
                                    .frame(maxWidth: .infinity)
                                    .padding(.vertical, 12)
                                    .background(Color.accent.opacity(viewModel.isAutoClassifying ? 0.5 : 1.0))
                                    .clipShape(RoundedRectangle(cornerRadius: 12))
                                }
                                .disabled(viewModel.isAutoClassifying)
                                .padding(.horizontal)
                            }
                        }

                        // Transaction list
                        LazyVStack(spacing: 8) {
                            ForEach(viewModel.transactions) { transaction in
                                ExpenseTransactionRow(transaction: transaction)
                                    .onTapGesture {
                                        viewModel.selectedTransaction = transaction
                                        viewModel.showClassificationSheet = true
                                    }
                            }

                            if viewModel.hasMore {
                                Button {
                                    Task { await viewModel.loadMore() }
                                } label: {
                                    Text("Load More")
                                        .font(.roundedBody)
                                        .foregroundStyle(Color.accent)
                                        .frame(maxWidth: .infinity)
                                        .padding()
                                }
                            }
                        }
                        .padding(.horizontal)

                        if viewModel.transactions.isEmpty && !viewModel.isLoading {
                            VStack(spacing: 12) {
                                Image(systemName: "tray")
                                    .font(.system(size: 40))
                                    .foregroundStyle(Color.textSecondary)
                                Text("No expenses found")
                                    .font(.roundedHeadline)
                                    .foregroundStyle(Color.textSecondary)
                                Text("Link a bank account or log an expense by voice")
                                    .font(.roundedCaption)
                                    .foregroundStyle(Color.textSecondary)
                            }
                            .padding(.top, 40)
                        }
                    }
                    .padding(.vertical)
                }

                // Voice logging button pinned to bottom
                voiceLogButton
            }
            .background(Color.appBackground)
            .navigationTitle("Expenses")
            .navigationBarTitleDisplayMode(.large)
            .refreshable {
                await viewModel.refresh()
            }
            .task {
                if viewModel.transactions.isEmpty {
                    await viewModel.refresh()
                }
            }
            .sheet(isPresented: $viewModel.showClassificationSheet) {
                if let transaction = viewModel.selectedTransaction {
                    TransactionClassificationSheet(
                        transaction: transaction,
                        viewModel: viewModel
                    )
                    .presentationDetents([.medium])
                    .presentationDragIndicator(.visible)
                }
            }
            .sheet(isPresented: $viewModel.showSplitSheet) {
                if let transaction = viewModel.splitTransaction {
                    SplitHalfSheet(transaction: transaction) { ratio in
                        viewModel.showSplitSheet = false
                        Task {
                            await viewModel.classifyViaSwipe(
                                transactionId: transaction.id,
                                classification: "mixed",
                                essentialRatio: ratio
                            )
                        }
                    }
                    .presentationDetents([.medium])
                    .presentationDragIndicator(.visible)
                }
            }
            .sheet(isPresented: $showVoiceRecording) {
                VoiceTransactionFlowView(viewModel: voiceViewModel) {
                    showVoiceRecording = false
                    Task { await viewModel.refresh() }
                }
            }
            .sheet(isPresented: $showReceiptScan) {
                ReceiptScanView(viewModel: receiptViewModel) {
                    showReceiptScan = false
                    receiptViewModel.reset()
                    Task { await viewModel.refresh() }
                }
            }
            .onChange(of: voiceViewModel.state) { _, newState in
                if newState == .success {
                    Task { await viewModel.refresh() }
                }
            }
        }
    }

    // MARK: - Bottom Action Buttons (Voice + Receipt)

    private var voiceLogButton: some View {
        HStack(spacing: 12) {
            // Voice log button
            Button {
                voiceViewModel.reset()
                showVoiceRecording = true
            } label: {
                HStack(spacing: 6) {
                    Image(systemName: "mic.fill")
                    Text("Voice")
                        .font(.roundedHeadline)
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, 14)
                .background(Color.accent)
                .foregroundStyle(Color.appBackground)
                .clipShape(Capsule())
            }

            // Scan receipt button
            Button {
                receiptViewModel.reset()
                showReceiptScan = true
            } label: {
                HStack(spacing: 6) {
                    Image(systemName: "receipt")
                    Text("Scan Receipt")
                        .font(.roundedHeadline)
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, 14)
                .background(Color.surface)
                .foregroundStyle(Color.accent)
                .clipShape(Capsule())
                .overlay(Capsule().stroke(Color.accent, lineWidth: 1))
            }
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 12)
        .background(Color.surface)
    }
}

// MARK: - Summary Card (3 segments: Essential / Fun Money / Unclassified)

struct ExpensesSummaryCard: View {
    let summary: ExpensesSummary

    private var total: Double {
        summary.totalEssential + summary.totalDiscretionary + summary.totalUnclassified
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Spending Breakdown")
                .font(.roundedHeadline)
                .foregroundStyle(Color.textPrimary)

            // Colored segment bar
            if total > 0 {
                GeometryReader { geometry in
                    HStack(spacing: 2) {
                        let width = geometry.size.width - 4 // account for spacing
                        segmentRect(color: .green, fraction: summary.totalEssential / total, width: width)
                        segmentRect(color: Color.danger, fraction: summary.totalDiscretionary / total, width: width)
                        segmentRect(color: .gray, fraction: summary.totalUnclassified / total, width: width)
                    }
                }
                .frame(height: 12)
                .clipShape(Capsule())
            }

            // Legend — single row
            HStack(spacing: 16) {
                legendItem(color: .green, label: "Essential", amount: summary.totalEssential)
                legendItem(color: Color.danger, label: "Fun Money", amount: summary.totalDiscretionary)
                legendItem(color: .gray, label: "Unclassified", amount: summary.totalUnclassified)
            }
        }
        .walletCard()
        .padding(.horizontal)
    }

    private func segmentRect(color: Color, fraction: Double, width: CGFloat) -> some View {
        RoundedRectangle(cornerRadius: 4)
            .fill(color)
            .frame(width: max(fraction * width, fraction > 0 ? 4 : 0))
    }

    private func legendItem(color: Color, label: String, amount: Double) -> some View {
        HStack(spacing: 6) {
            Circle()
                .fill(color)
                .frame(width: 8, height: 8)
            Text(label)
                .font(.roundedCaption)
                .foregroundStyle(Color.textSecondary)
            Text("$\(amount, specifier: "%.0f")")
                .font(.roundedCaption)
                .foregroundStyle(Color.textPrimary)
                .monospacedDigit()
        }
    }
}

// MARK: - Swipe Classification Card

struct SwipeClassificationCard: View {
    let transaction: UnclassifiedTransactionItem
    let remainingCount: Int
    let onClassify: (String, Double?) -> Void
    let onSplitRequest: () -> Void

    @State private var offset: CGSize = .zero

    private var swipeDirection: SwipeDirection {
        if offset.height < -80 { return .up }
        if offset.width > 100 { return .right }
        if offset.width < -100 { return .left }
        return .none
    }

    private enum SwipeDirection {
        case none, left, right, up
    }

    private var overlayColor: Color {
        switch swipeDirection {
        case .right: return .green
        case .left: return Color.danger
        case .up: return Color.accent
        case .none:
            if abs(offset.width) > abs(offset.height) {
                return offset.width > 0 ? .green : Color.danger
            } else if offset.height < 0 {
                return Color.accent
            }
            return .clear
        }
    }

    private var overlayOpacity: Double {
        let progress = max(abs(offset.width) / 100, abs(min(offset.height, 0)) / 80)
        return min(progress * 0.3, 0.3)
    }

    private var overlayLabel: String {
        switch swipeDirection {
        case .right: return "Essential"
        case .left: return "Fun Money"
        case .up: return "Split"
        case .none: return ""
        }
    }

    var body: some View {
        VStack(spacing: 8) {
            // Card
            VStack(spacing: 12) {
                Text(transaction.merchantName ?? transaction.name)
                    .font(.roundedHeadline)
                    .foregroundStyle(Color.textPrimary)

                Text("$\(transaction.amount, specifier: "%.2f")")
                    .font(.rounded(.title2, weight: .bold))
                    .foregroundStyle(Color.accent)
                    .monospacedDigit()

                if let dateStr = transaction.date {
                    Text(formatDate(dateStr))
                        .font(.roundedCaption)
                        .foregroundStyle(Color.textSecondary)
                }

                if let ctx = transaction.merchantContext, ctx.totalUnclassified > 1 {
                    Text("\(ctx.totalUnclassified - 1) more from this merchant")
                        .font(.roundedCaption)
                        .foregroundStyle(Color.textSecondary)
                }

                // Overlay label during drag
                if !overlayLabel.isEmpty {
                    Text(overlayLabel)
                        .font(.rounded(.title3, weight: .bold))
                        .foregroundStyle(overlayColor)
                        .opacity(min(max(abs(offset.width) / 100, abs(min(offset.height, 0)) / 80), 1.0))
                }
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 20)
            .background(
                RoundedRectangle(cornerRadius: 16)
                    .fill(Color.surface)
                    .overlay(
                        RoundedRectangle(cornerRadius: 16)
                            .fill(overlayColor.opacity(overlayOpacity))
                    )
            )
            .offset(x: offset.width, y: offset.height)
            .rotationEffect(.degrees(Double(offset.width) / 20))
            .gesture(
                DragGesture()
                    .onChanged { value in
                        offset = value.translation
                    }
                    .onEnded { value in
                        let dir = swipeDirection
                        withAnimation(.spring(response: 0.3)) {
                            switch dir {
                            case .right:
                                offset = CGSize(width: 500, height: 0)
                                onClassify("essential", nil)
                            case .left:
                                offset = CGSize(width: -500, height: 0)
                                onClassify("discretionary", nil)
                            case .up:
                                offset = CGSize(width: 0, height: -500)
                                onSplitRequest()
                            case .none:
                                offset = .zero
                            }
                        }
                        // Reset offset after animation
                        DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) {
                            offset = .zero
                        }
                    }
            )

            // Hint icons
            HStack {
                HStack(spacing: 4) {
                    Image(systemName: "arrow.left")
                    Text("Fun Money")
                }
                .font(.roundedCaption)
                .foregroundStyle(Color.danger.opacity(0.6))

                Spacer()

                HStack(spacing: 4) {
                    Image(systemName: "arrow.up")
                    Text("Split")
                }
                .font(.roundedCaption)
                .foregroundStyle(Color.accent.opacity(0.6))

                Spacer()

                HStack(spacing: 4) {
                    Text("Essential")
                    Image(systemName: "arrow.right")
                }
                .font(.roundedCaption)
                .foregroundStyle(Color.green.opacity(0.6))
            }
            .padding(.horizontal, 4)

            // Counter
            Text("\(remainingCount) transactions to classify")
                .font(.roundedCaption)
                .foregroundStyle(Color.textSecondary)
        }
        .walletCard()
        .padding(.horizontal)
    }

    private func formatDate(_ dateStr: String) -> String {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        guard let date = formatter.date(from: dateStr) else { return dateStr }
        formatter.dateFormat = "MMM d, yyyy"
        return formatter.string(from: date)
    }
}

// MARK: - Split Half-Sheet

struct SplitHalfSheet: View {
    let transaction: UnclassifiedTransactionItem
    let onConfirm: (Double) -> Void

    @State private var essentialRatio: Double = 0.5
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            VStack(spacing: 20) {
                // Transaction details
                VStack(spacing: 6) {
                    Text(transaction.merchantName ?? transaction.name)
                        .font(.roundedHeadline)
                        .foregroundStyle(Color.textPrimary)

                    Text("$\(transaction.amount, specifier: "%.2f")")
                        .font(.rounded(.title, weight: .bold))
                        .foregroundStyle(Color.accent)
                        .monospacedDigit()
                }
                .padding(.top)

                // Slider
                VStack(spacing: 8) {
                    HStack {
                        Text("Essential")
                            .font(.roundedCaption)
                            .foregroundStyle(.green)
                        Spacer()
                        Text("\(Int(essentialRatio * 100))%")
                            .font(.roundedBody)
                            .fontWeight(.medium)
                            .foregroundStyle(Color.textPrimary)
                            .monospacedDigit()
                        Spacer()
                        Text("Fun Money")
                            .font(.roundedCaption)
                            .foregroundStyle(Color.danger)
                    }

                    Slider(value: $essentialRatio, in: 0...1, step: 0.05)
                        .tint(Color.accent)

                    // Live split preview
                    HStack {
                        Text("$\(transaction.amount * essentialRatio, specifier: "%.2f") Essential")
                            .font(.roundedCaption)
                            .foregroundStyle(.green)
                        Spacer()
                        Text("$\(transaction.amount * (1 - essentialRatio), specifier: "%.2f") Fun Money")
                            .font(.roundedCaption)
                            .foregroundStyle(Color.danger)
                    }
                }
                .padding(.horizontal)

                // Confirm button
                Button {
                    onConfirm(essentialRatio)
                } label: {
                    Text("Confirm Split")
                        .font(.roundedBody)
                        .fontWeight(.semibold)
                        .foregroundStyle(.white)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 14)
                        .background(Color.accent)
                        .clipShape(RoundedRectangle(cornerRadius: 12))
                }
                .padding(.horizontal)

                Spacer()
            }
            .background(Color.appBackground)
            .navigationTitle("Split Transaction")
            .navigationBarTitleDisplayMode(.inline)
            .toolbarColorScheme(.dark, for: .navigationBar)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                        .foregroundStyle(Color.accent)
                }
            }
        }
    }
}

// MARK: - Proportional Split Badge

struct SplitBadge: View {
    let essentialRatio: Double

    var body: some View {
        GeometryReader { geo in
            HStack(spacing: 0) {
                Color.green.frame(width: geo.size.width * essentialRatio)
                Color.danger.frame(width: geo.size.width * (1 - essentialRatio))
            }
        }
        .frame(width: 48, height: 14)
        .clipShape(Capsule())
    }
}

// MARK: - Transaction Row

struct ExpenseTransactionRow: View {
    let transaction: ExpenseTransaction

    var body: some View {
        HStack(spacing: 12) {
            VStack(alignment: .leading, spacing: 4) {
                Text(transaction.merchantName ?? transaction.name)
                    .font(.roundedBody)
                    .foregroundStyle(Color.textPrimary)
                    .lineLimit(1)

                if let dateStr = transaction.date {
                    Text(formatDate(dateStr))
                        .font(.roundedCaption)
                        .foregroundStyle(Color.textSecondary)
                }
            }

            Spacer()

            VStack(alignment: .trailing, spacing: 4) {
                Text("$\(transaction.amount, specifier: "%.2f")")
                    .font(.roundedBody)
                    .fontWeight(.medium)
                    .foregroundStyle(Color.textPrimary)
                    .monospacedDigit()

                transactionBadge
            }
        }
        .padding(12)
        .background(Color.surface)
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }

    @ViewBuilder
    private var transactionBadge: some View {
        switch transaction.subCategory {
        case "essential":
            textBadge("Essential", color: .green)
        case "discretionary":
            textBadge("Fun Money", color: Color.danger)
        case "mixed":
            SplitBadge(essentialRatio: splitRatio)
        default:
            textBadge("Unclassified", color: .gray)
        }
    }

    private var splitRatio: Double {
        guard let ea = transaction.essentialAmount, transaction.amount > 0 else { return 0.5 }
        return ea / abs(transaction.amount)
    }

    private func textBadge(_ label: String, color: Color) -> some View {
        Text(label)
            .font(.system(size: 10, weight: .semibold, design: .rounded))
            .foregroundStyle(.white)
            .padding(.horizontal, 8)
            .padding(.vertical, 3)
            .background(color.opacity(0.8))
            .clipShape(Capsule())
    }

    private func formatDate(_ dateStr: String) -> String {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        guard let date = formatter.date(from: dateStr) else { return dateStr }
        formatter.dateFormat = "MMM d, yyyy"
        return formatter.string(from: date)
    }
}

// MARK: - Transaction Classification Sheet

struct TransactionClassificationSheet: View {
    let transaction: ExpenseTransaction
    @Bindable var viewModel: ExpensesViewModel

    @State private var selectedCategory: String
    @State private var essentialRatio: Double
    @State private var isSaving = false
    @State private var showChallenge = false
    @State private var challengeReason = ""
    @Environment(\.dismiss) private var dismiss

    init(transaction: ExpenseTransaction, viewModel: ExpensesViewModel) {
        self.transaction = transaction
        self.viewModel = viewModel
        _selectedCategory = State(initialValue: transaction.subCategory == "unclassified" ? "mixed" : transaction.subCategory)
        let currentRatio: Double = if let ea = transaction.essentialAmount, transaction.amount > 0 {
            ea / abs(transaction.amount)
        } else {
            0.5
        }
        _essentialRatio = State(initialValue: currentRatio)
    }

    var body: some View {
        NavigationStack {
            VStack(spacing: 20) {
                // Transaction details
                VStack(spacing: 6) {
                    Text(transaction.merchantName ?? transaction.name)
                        .font(.roundedHeadline)
                        .foregroundStyle(Color.textPrimary)

                    Text("$\(transaction.amount, specifier: "%.2f")")
                        .font(.rounded(.title, weight: .bold))
                        .foregroundStyle(Color.accent)
                        .monospacedDigit()

                    if let dateStr = transaction.date {
                        Text(dateStr)
                            .font(.roundedCaption)
                            .foregroundStyle(Color.textSecondary)
                    }
                }
                .padding(.top)

                // Category picker — Essential | Fun Money | Split
                Picker("Classification", selection: $selectedCategory) {
                    Text("Essential").tag("essential")
                    Text("Fun Money").tag("discretionary")
                    Text("Split").tag("mixed")
                }
                .pickerStyle(.segmented)
                .padding(.horizontal)
                .onChange(of: selectedCategory) {
                    switch selectedCategory {
                    case "essential": essentialRatio = 1.0
                    case "discretionary": essentialRatio = 0.0
                    default: break
                    }
                }

                // Slider for split
                if selectedCategory == "mixed" {
                    VStack(spacing: 8) {
                        HStack {
                            Text("Essential")
                                .font(.roundedCaption)
                                .foregroundStyle(.green)
                            Spacer()
                            Text("\(Int(essentialRatio * 100))%")
                                .font(.roundedBody)
                                .fontWeight(.medium)
                                .foregroundStyle(Color.textPrimary)
                                .monospacedDigit()
                            Spacer()
                            Text("Fun Money")
                                .font(.roundedCaption)
                                .foregroundStyle(Color.danger)
                        }

                        Slider(value: $essentialRatio, in: 0...1, step: 0.05)
                            .tint(Color.accent)

                        HStack {
                            Text("$\(transaction.amount * essentialRatio, specifier: "%.2f") essential")
                                .font(.roundedCaption)
                                .foregroundStyle(.green)
                            Spacer()
                            Text("$\(transaction.amount * (1 - essentialRatio), specifier: "%.2f") fun money")
                                .font(.roundedCaption)
                                .foregroundStyle(Color.danger)
                        }
                    }
                    .padding(.horizontal)
                }

                Spacer()
            }
            .background(Color.appBackground)
            .navigationTitle("Classify Transaction")
            .navigationBarTitleDisplayMode(.inline)
            .toolbarColorScheme(.dark, for: .navigationBar)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                        .foregroundStyle(Color.textSecondary)
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button(isSaving ? "Saving..." : "Save") {
                        let ratio: Double? = selectedCategory == "mixed" ? essentialRatio : nil
                        isSaving = true
                        Task {
                            do {
                                let response = try await viewModel.classifyTransactionForSheet(
                                    transactionId: transaction.id,
                                    subCategory: selectedCategory,
                                    essentialRatio: ratio
                                )
                                if let challenge = response.challenge, challenge.show, let reason = challenge.reason {
                                    challengeReason = reason
                                    showChallenge = true
                                } else {
                                    dismiss()
                                }
                            } catch {
                                print("Failed to classify: \(error)")
                            }
                            isSaving = false
                        }
                    }
                    .disabled(isSaving)
                    .foregroundStyle(Color.accent)
                }
            }
            .alert("Are you sure?", isPresented: $showChallenge) {
                Button("Yes, it's Essential") { dismiss() }
                Button("Change to Discretionary") {
                    Task {
                        _ = try? await viewModel.classifyTransactionForSheet(
                            transactionId: transaction.id,
                            subCategory: "discretionary",
                            essentialRatio: 0.0
                        )
                        dismiss()
                    }
                }
            } message: {
                Text(challengeReason)
            }
        }
    }
}

#Preview {
    ExpensesView(viewModel: ExpensesViewModel())
}
