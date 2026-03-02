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
    @State private var showAddOptions = false

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

                        // Date range indicator
                        if !viewModel.rangeLabel.isEmpty {
                            Text(viewModel.rangeLabel)
                                .font(.roundedCaption)
                                .foregroundStyle(Color.textSecondary)
                                .frame(maxWidth: .infinity, alignment: .leading)
                                .padding(.horizontal)
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

                        // Transaction list grouped by week
                        LazyVStack(spacing: 8) {
                            if viewModel.isLoading && viewModel.transactions.isEmpty {
                                ForEach(0..<7, id: \.self) { i in
                                    SkeletonExpenseRow(delay: Double(i) * 0.07)
                                }
                            } else {
                                ForEach(viewModel.transactionsByWeek, id: \.label) { section in
                                    // Week header
                                    HStack {
                                        Text(section.label)
                                            .font(.system(size: 12, weight: .semibold, design: .rounded))
                                            .foregroundStyle(Color.textSecondary)
                                            .textCase(.uppercase)
                                        Spacer()
                                    }
                                    .padding(.horizontal, 4)
                                    .padding(.top, section.label == viewModel.transactionsByWeek.first?.label ? 0 : 8)

                                    ForEach(section.items) { transaction in
                                        ExpenseTransactionRow(transaction: transaction)
                                            .onTapGesture {
                                                viewModel.selectedTransaction = transaction
                                                viewModel.showClassificationSheet = true
                                            }
                                    }
                                }

                                // Load Previous Week button
                                Button {
                                    Task { await viewModel.loadPreviousWeek() }
                                } label: {
                                    HStack(spacing: 8) {
                                        if viewModel.isLoadingMore {
                                            ProgressView()
                                                .tint(Color.accent)
                                                .scaleEffect(0.8)
                                        }
                                        Text(viewModel.isLoadingMore ? "Loading..." : viewModel.canLoadMore ? "Load Previous Week" : "No more history")
                                            .font(.roundedBody)
                                            .foregroundStyle(viewModel.canLoadMore ? Color.accent : Color.textSecondary)
                                    }
                                    .frame(maxWidth: .infinity)
                                    .padding(.vertical, 12)
                                }
                                .disabled(viewModel.isLoadingMore || !viewModel.canLoadMore)
                                .padding(.top, 4)
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
                                Text("Link a bank account or log a transaction")
                                    .font(.roundedCaption)
                                    .foregroundStyle(Color.textSecondary)
                            }
                            .padding(.top, 40)
                        }
                    }
                    .padding(.vertical)
                }

                // Log transaction button pinned to bottom
                logTransactionButton
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
                    let hasReceipt = !(transaction.receiptItems?.isEmpty ?? true)
                    TransactionClassificationSheet(
                        transaction: transaction,
                        viewModel: viewModel
                    )
                    .presentationDetents(hasReceipt ? [.large] : [.medium])
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

    // MARK: - Log Transaction Button

    private var logTransactionButton: some View {
        Button {
            showAddOptions = true
        } label: {
            HStack(spacing: 8) {
                Image(systemName: "plus")
                    .font(.system(size: 16, weight: .bold))
                Text("Add Transaction")
                    .font(.roundedHeadline)
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 14)
            .background(Color.accent)
            .foregroundStyle(Color.appBackground)
            .clipShape(Capsule())
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 12)
        .background(Color.surface)
        .confirmationDialog("Add Transaction", isPresented: $showAddOptions, titleVisibility: .visible) {
            Button {
                voiceViewModel.reset()
                showVoiceRecording = true
            } label: {
                Label("Voice", systemImage: "mic.fill")
            }

            Button {
                voiceViewModel.startManualEntry()
                showVoiceRecording = true
            } label: {
                Label("Manual Entry", systemImage: "square.and.pencil")
            }

            Button {
                receiptViewModel.reset()
                showReceiptScan = true
            } label: {
                Label("Scan Receipt", systemImage: "receipt")
            }

            Button("Cancel", role: .cancel) {}
        }
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
    @State private var hintOffset: CGFloat = 0

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
            .offset(x: offset.width + hintOffset, y: offset.height)
            .rotationEffect(.degrees(Double(offset.width + hintOffset) / 20))
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
        .onAppear {
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.7) { playHintAnimation() }
        }
        .onChange(of: transaction.id) {
            hintOffset = 0
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.4) { playHintAnimation() }
        }
    }

    private func playHintAnimation() {
        withAnimation(.easeOut(duration: 0.18)) { hintOffset = 26 }
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.18) {
            withAnimation(.easeInOut(duration: 0.2)) { hintOffset = -26 }
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.2) {
                withAnimation(.easeInOut(duration: 0.18)) { hintOffset = 16 }
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.18) {
                    withAnimation(.spring(response: 0.35, dampingFraction: 0.55)) { hintOffset = 0 }
                }
            }
        }
    }

    private func formatDate(_ dateStr: String) -> String {
        expensesFormatDate(dateStr)
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
        let ess = transaction.essentialAmount ?? 0
        let disc = transaction.discretionaryAmount ?? 0
        if transaction.subCategory == "unclassified" || (ess < 0.01 && disc < 0.01) {
            textBadge("Unclassified", color: .gray)
        } else if disc < 0.01 {
            textBadge("Essential", color: .green)
        } else if ess < 0.01 {
            textBadge("Fun Money", color: Color.danger)
        } else {
            SplitBadge(essentialRatio: transaction.amount > 0 ? ess / abs(transaction.amount) : 0.5)
        }
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
        expensesFormatDate(dateStr)
    }
}

// MARK: - Transaction Classification Sheet

struct TransactionClassificationSheet: View {
    let transaction: ExpenseTransaction
    @Bindable var viewModel: ExpensesViewModel

    @State private var selectedCategory: String
    @State private var essentialRatio: Double
    @State private var classifications: [String]   // per-item overrides for receipt mode
    @State private var isSaving = false
    @State private var showChallenge = false
    @State private var challengeReason = ""
    @Environment(\.dismiss) private var dismiss

    private var hasReceiptItems: Bool { !(transaction.receiptItems?.isEmpty ?? true) }

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
        _classifications = State(initialValue: transaction.receiptItems?.map(\.classification) ?? [])
    }

    // Live totals driven by per-item classification toggles
    private var currentEssentialTotal: Double {
        guard let items = transaction.receiptItems else { return transaction.essentialAmount ?? 0 }
        return zip(items, classifications).reduce(0) { $0 + ($1.1 == "essential" ? $1.0.price : 0) }
    }
    private var currentDiscretionaryTotal: Double {
        guard let items = transaction.receiptItems else { return transaction.discretionaryAmount ?? 0 }
        return zip(items, classifications).reduce(0) { $0 + ($1.1 == "discretionary" ? $1.0.price : 0) }
    }

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                ScrollView {
                    VStack(spacing: 16) {
                        headerCard
                        if hasReceiptItems {
                            receiptItemsSection
                        } else {
                            classificationSection
                        }
                    }
                    .padding(.vertical, 16)
                }
                saveButton
            }
            .background(Color.appBackground)
            .navigationTitle("Transaction Details")
            .navigationBarTitleDisplayMode(.inline)
            .toolbarColorScheme(.dark, for: .navigationBar)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                        .foregroundStyle(Color.textSecondary)
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

    // MARK: - Header card

    private var headerCard: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(alignment: .top) {
                VStack(alignment: .leading, spacing: 4) {
                    Text(transaction.merchantName ?? transaction.name)
                        .font(.roundedHeadline)
                        .foregroundStyle(Color.textPrimary)
                    if let dateStr = transaction.date {
                        Text(expensesFormatDate(dateStr))
                            .font(.roundedCaption)
                            .foregroundStyle(Color.textSecondary)
                    }
                }
                Spacer()
                VStack(alignment: .trailing, spacing: 6) {
                    Text("$\(transaction.amount, specifier: "%.2f")")
                        .font(.rounded(.title2, weight: .bold))
                        .foregroundStyle(Color.accent)
                        .monospacedDigit()
                    sourceBadge
                }
            }

            // Plaid category
            if let cat = transaction.categoryDetailed ?? transaction.categoryPrimary,
               !cat.isEmpty, transaction.source == nil || transaction.source == "plaid" {
                Text(cat.replacingOccurrences(of: "_", with: " ").capitalized)
                    .font(.roundedCaption)
                    .foregroundStyle(Color.textSecondary)
            }

            // Voice / receipt notes
            if let notes = transaction.notes, !notes.isEmpty {
                Divider()
                Text(notes)
                    .font(.roundedBody)
                    .foregroundStyle(Color.textSecondary)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }

            // Live split bar (receipt mode only)
            if hasReceiptItems, transaction.amount > 0 {
                let essentialFraction = currentEssentialTotal / transaction.amount
                Divider()
                GeometryReader { geo in
                    HStack(spacing: 2) {
                        Color.accent
                            .frame(width: max(essentialFraction * geo.size.width, essentialFraction > 0 ? 4 : 0))
                        Color.danger
                            .frame(width: max((1 - essentialFraction) * geo.size.width, (1 - essentialFraction) > 0 ? 4 : 0))
                    }
                }
                .frame(height: 10)
                .clipShape(Capsule())
                .animation(.easeInOut(duration: 0.25), value: currentEssentialTotal)

                HStack {
                    HStack(spacing: 4) {
                        Circle().fill(Color.accent).frame(width: 8, height: 8)
                        Text("Essential $\(currentEssentialTotal, specifier: "%.2f")")
                            .font(.roundedCaption).foregroundStyle(Color.textSecondary).monospacedDigit()
                    }
                    Spacer()
                    HStack(spacing: 4) {
                        Circle().fill(Color.danger).frame(width: 8, height: 8)
                        Text("Fun Money $\(currentDiscretionaryTotal, specifier: "%.2f")")
                            .font(.roundedCaption).foregroundStyle(Color.textSecondary).monospacedDigit()
                    }
                }
            }
        }
        .padding(16)
        .background(Color.surface)
        .clipShape(RoundedRectangle(cornerRadius: 16))
        .padding(.horizontal)
    }

    @ViewBuilder
    private var sourceBadge: some View {
        let src = transaction.source ?? "plaid"
        HStack(spacing: 4) {
            Image(systemName: src == "receipt" ? "receipt" : src == "voice" ? "mic.fill" : "building.columns")
                .font(.system(size: 9))
            Text(src == "receipt" ? "Receipt" : src == "voice" ? "Voice" : "Plaid")
                .font(.system(size: 10, weight: .semibold, design: .rounded))
        }
        .foregroundStyle(.white)
        .padding(.horizontal, 8)
        .padding(.vertical, 4)
        .background(src == "receipt" ? Color.accent : src == "voice" ? Color.orange : Color.indigo)
        .clipShape(Capsule())
    }

    // MARK: - Receipt line items (tappable)

    private var receiptItemsSection: some View {
        VStack(spacing: 16) {
            HStack(spacing: 5) {
                Image(systemName: "hand.tap")
                    .font(.system(size: 12))
                Text("Tap items to change their category")
                    .font(.roundedCaption)
            }
            .foregroundStyle(Color.textSecondary)
            .padding(.horizontal, 12)
            .padding(.vertical, 7)
            .background(Color.appBackground)
            .clipShape(Capsule())
            .overlay(Capsule().stroke(Color.textSecondary.opacity(0.18), lineWidth: 1))

            ForEach(Array((transaction.receiptItems ?? []).enumerated()), id: \.offset) { index, item in
                let cls = index < classifications.count ? classifications[index] : item.classification
                let isEssential = cls == "essential"
                Button {
                    withAnimation(.easeInOut(duration: 0.2)) {
                        if index < classifications.count {
                            classifications[index] = isEssential ? "discretionary" : "essential"
                        }
                    }
                } label: {
                    HStack(spacing: 12) {
                        RoundedRectangle(cornerRadius: 3)
                            .fill(isEssential ? Color.accent : Color.danger)
                            .frame(width: 4)
                            .padding(.vertical, 2)
                        Text(item.name)
                            .font(.roundedBody)
                            .foregroundStyle(Color.textPrimary)
                            .lineLimit(2)
                            .multilineTextAlignment(.leading)
                            .frame(maxWidth: .infinity, alignment: .leading)
                        VStack(alignment: .trailing, spacing: 2) {
                            Text("$\(item.price, specifier: "%.2f")")
                                .font(.roundedBody).fontWeight(.medium)
                                .foregroundStyle(Color.textPrimary).monospacedDigit()
                            Text(isEssential ? "Essential" : "Fun Money")
                                .font(.system(size: 10, weight: .semibold, design: .rounded))
                                .foregroundStyle(isEssential ? Color.accent : Color.danger)
                        }
                    }
                    .padding(.horizontal, 16)
                    .padding(.vertical, 10)
                    .background(Color.surface)
                    .clipShape(RoundedRectangle(cornerRadius: 12))
                }
                .buttonStyle(.plain)
            }
        }
        .padding(.horizontal)
    }

    // MARK: - Standard classification picker

    private var classificationSection: some View {
        VStack(spacing: 16) {
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

            if selectedCategory == "mixed" {
                VStack(spacing: 8) {
                    HStack {
                        Text("Essential").font(.roundedCaption).foregroundStyle(.green)
                        Spacer()
                        Text("\(Int(essentialRatio * 100))%")
                            .font(.roundedBody).fontWeight(.medium)
                            .foregroundStyle(Color.textPrimary).monospacedDigit()
                        Spacer()
                        Text("Fun Money").font(.roundedCaption).foregroundStyle(Color.danger)
                    }
                    Slider(value: $essentialRatio, in: 0...1, step: 0.05).tint(Color.accent)
                    HStack {
                        Text("$\(transaction.amount * essentialRatio, specifier: "%.2f") essential")
                            .font(.roundedCaption).foregroundStyle(.green)
                        Spacer()
                        Text("$\(transaction.amount * (1 - essentialRatio), specifier: "%.2f") fun money")
                            .font(.roundedCaption).foregroundStyle(Color.danger)
                    }
                }
                .padding(.horizontal)
            }
        }
    }

    // MARK: - Save button

    private var saveButton: some View {
        Button {
            guard !isSaving else { return }
            isSaving = true
            Task {
                do {
                    let subCat: String
                    let ratio: Double
                    if hasReceiptItems {
                        ratio = transaction.amount > 0 ? currentEssentialTotal / transaction.amount : 0.5
                        subCat = currentDiscretionaryTotal < 0.01 ? "essential"
                               : currentEssentialTotal < 0.01 ? "discretionary"
                               : "mixed"
                    } else {
                        ratio = selectedCategory == "mixed" ? essentialRatio
                              : selectedCategory == "essential" ? 1.0 : 0.0
                        subCat = selectedCategory
                    }
                    let response = try await viewModel.classifyTransactionForSheet(
                        transactionId: transaction.id,
                        subCategory: subCat,
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
        } label: {
            Text(isSaving ? "Saving..." : "Save")
                .font(.roundedHeadline).fontWeight(.semibold)
                .foregroundStyle(.white)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 14)
                .background(isSaving ? Color.accent.opacity(0.5) : Color.accent)
                .clipShape(RoundedRectangle(cornerRadius: 14))
        }
        .disabled(isSaving)
        .padding(.horizontal)
        .padding(.vertical, 12)
        .background(Color.surface)
    }
}

// MARK: - Skeleton Loading Row

struct SkeletonExpenseRow: View {
    let delay: Double
    @State private var opacity: Double = 0.3

    var body: some View {
        HStack(spacing: 12) {
            VStack(alignment: .leading, spacing: 7) {
                RoundedRectangle(cornerRadius: 4)
                    .fill(Color.textSecondary.opacity(0.35))
                    .frame(width: 130, height: 13)
                RoundedRectangle(cornerRadius: 4)
                    .fill(Color.textSecondary.opacity(0.25))
                    .frame(width: 80, height: 10)
            }
            Spacer()
            VStack(alignment: .trailing, spacing: 7) {
                RoundedRectangle(cornerRadius: 4)
                    .fill(Color.textSecondary.opacity(0.35))
                    .frame(width: 55, height: 13)
                Capsule()
                    .fill(Color.textSecondary.opacity(0.25))
                    .frame(width: 52, height: 18)
            }
        }
        .padding(12)
        .background(Color.surface)
        .clipShape(RoundedRectangle(cornerRadius: 12))
        .opacity(opacity)
        .onAppear {
            DispatchQueue.main.asyncAfter(deadline: .now() + delay) {
                withAnimation(.easeInOut(duration: 0.75).repeatForever(autoreverses: true)) {
                    opacity = 0.9
                }
            }
        }
    }
}

// MARK: - Shared Date Formatter

private func expensesFormatDate(_ dateStr: String) -> String {
    // Try ISO8601 with time component first (e.g. "2026-02-26T20:24:13Z")
    let iso = ISO8601DateFormatter()
    if let date = iso.date(from: dateStr) {
        let df = DateFormatter()
        df.dateFormat = "MMM d, yyyy"
        return df.string(from: date)
    }
    // Fall back to plain date "yyyy-MM-dd"
    let df = DateFormatter()
    df.dateFormat = "yyyy-MM-dd"
    if let date = df.date(from: dateStr) {
        df.dateFormat = "MMM d, yyyy"
        return df.string(from: date)
    }
    return dateStr
}

#Preview {
    ExpensesView(viewModel: ExpensesViewModel())
}
