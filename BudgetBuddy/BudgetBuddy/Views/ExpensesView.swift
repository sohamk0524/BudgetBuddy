//
//  ExpensesView.swift
//  BudgetBuddy
//
//  Expenses tab with category-based classification
//

import SwiftUI

@MainActor
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

                        // Filter chips (horizontally scrollable)
                        ScrollView(.horizontal, showsIndicators: false) {
                            HStack(spacing: 8) {
                                ForEach(ExpenseFilter.allFilters(hasUnclassified: viewModel.hasUnclassified), id: \.self) { filter in
                                    Button {
                                        if filter != .all && viewModel.selectedFilter == filter {
                                            viewModel.selectedFilter = .all
                                        } else {
                                            viewModel.selectedFilter = filter
                                        }
                                    } label: {
                                        Text(filter.displayName)
                                            .font(.roundedCaption)
                                            .foregroundStyle(viewModel.selectedFilter == filter ? Color.appBackground : Color.textPrimary)
                                            .padding(.horizontal, 14)
                                            .padding(.vertical, 7)
                                            .background(viewModel.selectedFilter == filter ? Color.accent : Color.surface)
                                            .clipShape(Capsule())
                                    }
                                }
                            }
                            .padding(.horizontal)
                        }

                        // Date range indicator
                        if !viewModel.rangeLabel.isEmpty {
                            Text(viewModel.rangeLabel)
                                .font(.roundedCaption)
                                .foregroundStyle(Color.textSecondary)
                                .frame(maxWidth: .infinity, alignment: .leading)
                                .padding(.horizontal)
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
                                                AnalyticsManager.logTransactionTapped()
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
                AnalyticsManager.logExpensesViewed()
            }
            .sheet(isPresented: $viewModel.showClassificationSheet) {
                if let transaction = viewModel.selectedTransaction {
                    TransactionClassificationSheet(
                        transaction: transaction,
                        viewModel: viewModel
                    )
                    .presentationDetents([.medium, .large])
                    .presentationDragIndicator(.visible)
                }
            }
            .sheet(isPresented: $showVoiceRecording) {
                VoiceTransactionFlowView(viewModel: voiceViewModel) {
                    showVoiceRecording = false
                    // Background sync for eventual consistency
                    Task { await viewModel.refresh() }
                }
            }
            .sheet(isPresented: $showReceiptScan) {
                ReceiptScanView(viewModel: receiptViewModel) {
                    showReceiptScan = false
                    receiptViewModel.reset()
                    // Background sync for eventual consistency
                    Task { await viewModel.refresh() }
                }
            }
            .onReceive(NotificationCenter.default.publisher(for: .transactionAdded)) { notification in
                // Optimistic local insert — transaction appears instantly
                if let txn = notification.userInfo?["transaction"] as? ExpenseTransaction {
                    viewModel.insertTransactionLocally(txn)
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
                AnalyticsManager.logExpenseAdded(method: .voice)
            } label: {
                Label("Voice", systemImage: "mic.fill")
            }

            Button {
                voiceViewModel.startManualEntry()
                showVoiceRecording = true
                AnalyticsManager.logExpenseAdded(method: .manual)
            } label: {
                Label("Manual Entry", systemImage: "square.and.pencil")
            }

            Button {
                receiptViewModel.reset()
                showReceiptScan = true
                AnalyticsManager.logExpenseAdded(method: .receipt)
            } label: {
                Label("Scan Receipt", systemImage: "receipt")
            }

            Button("Cancel", role: .cancel) {}
        }
    }
}

// MARK: - Category Helpers

/// Maps legacy or unknown category strings to valid display categories.
@MainActor func normalizedItemCategory(_ raw: String) -> String {
    CategoryManager.shared.isValidCategory(raw) ? raw.lowercased() : "other"
}

@MainActor func categoryColor(for category: String) -> Color {
    CategoryManager.shared.color(for: category)
}

@MainActor func categoryIcon(for category: String) -> String {
    CategoryManager.shared.icon(for: category)
}

// MARK: - Summary Card (category-based)

struct ExpensesSummaryCard: View {
    let summary: ExpensesSummary

    private var segments: [(label: String, amount: Double, color: Color)] {
        var result: [(String, Double, Color)] = CategoryManager.shared.categories.map { cat in
            (cat.displayName, summary.categoryTotals[cat.name] ?? 0, categoryColor(for: cat.name))
        }
        result.append(("Unclassified", summary.totalUnclassified, .gray))
        return result.filter { $0.1 > 0 }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Spending Breakdown")
                .font(.roundedHeadline)
                .foregroundStyle(Color.textPrimary)

            if segments.isEmpty {
                // Empty state
                VStack(spacing: 8) {
                    Image(systemName: "chart.bar")
                        .font(.system(size: 28))
                        .foregroundStyle(Color.textSecondary.opacity(0.5))
                    Text("No spending data yet")
                        .font(.roundedCaption)
                        .foregroundStyle(Color.textSecondary)
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, 12)
            } else {
                // Colored segment bar
                if summary.total > 0 {
                    GeometryReader { geometry in
                        HStack(spacing: 2) {
                            let width = geometry.size.width - CGFloat(max(segments.count - 1, 0)) * 2
                            ForEach(segments, id: \.label) { seg in
                                RoundedRectangle(cornerRadius: 4)
                                    .fill(seg.color)
                                    .frame(width: max(seg.amount / summary.total * width, 4))
                            }
                        }
                    }
                    .frame(height: 12)
                    .clipShape(Capsule())
                }

                // Legend — wrap into rows of 3
                let row1 = segments.prefix(3)
                let row2 = segments.dropFirst(3)

                HStack(spacing: 16) {
                    ForEach(Array(row1), id: \.label) { seg in
                        legendItem(color: seg.color, label: seg.label, amount: seg.amount)
                    }
                }
                if !row2.isEmpty {
                    HStack(spacing: 16) {
                        ForEach(Array(row2), id: \.label) { seg in
                            legendItem(color: seg.color, label: seg.label, amount: seg.amount)
                        }
                    }
                }
            }
        }
        .walletCard()
        .padding(.horizontal)
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

                categoryBadge
            }
        }
        .padding(12)
        .background(Color.surface)
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }

    @ViewBuilder
    private var categoryBadge: some View {
        let cat = transaction.subCategory.lowercased()
        if cat.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            textBadge("Unclassified", color: .gray)
        } else if CategoryManager.shared.isValidCategory(cat) {
            textBadge(CategoryManager.shared.displayName(for: cat), color: categoryColor(for: cat))
        } else {
            // Orphaned category (deleted custom) — show as Other
            textBadge("Other", color: categoryColor(for: "other"))
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
    @State private var isSaving = false
    @State private var showDeleteTxnConfirm = false
    @State private var localItems: [EditableReceiptItem]   // draft — synced to backend on Save
    @State private var localItemsModified = false
    @State private var editedMerchant: String
    @State private var editedAmount: String
    @State private var editedDate: Date
    @State private var isEditing = false
    @Environment(\.dismiss) private var dismiss

    private var categories: [String] {
        CategoryManager.shared.categories.map { $0.displayName }
    }

    init(transaction: ExpenseTransaction, viewModel: ExpensesViewModel) {
        self.transaction = transaction
        self.viewModel = viewModel
        let current = transaction.subCategory.lowercased()
        _selectedCategory = State(initialValue: CategoryManager.shared.isValidCategory(current) ? CategoryManager.shared.displayName(for: current) : "")
        _localItems = State(initialValue: (transaction.receiptItems ?? []).map {
            EditableReceiptItem(name: $0.name, price: $0.price,
                                category: normalizedItemCategory($0.category))
        })
        _editedMerchant = State(initialValue: transaction.merchantName ?? transaction.name)
        _editedAmount = State(initialValue: String(format: "%.2f", transaction.amount))

        // Parse ISO date string into Date for DatePicker
        let dateFmt = DateFormatter()
        dateFmt.dateFormat = "yyyy-MM-dd"
        let parsedDate = transaction.date.flatMap { dateFmt.date(from: $0) } ?? Date()
        _editedDate = State(initialValue: parsedDate)
    }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 16) {
                    headerCard
                    categorySection
                    TransactionItemsSection(items: $localItems, readOnly: !isEditing)
                        .onChange(of: localItems) { _, _ in localItemsModified = true }
                    if isEditing {
                        deleteTransactionSection
                    }
                }
                .padding(.vertical, 16)
            }
            .background(Color.appBackground)
            .navigationTitle("Transaction Details")
            .navigationBarTitleDisplayMode(.inline)
            .toolbarColorScheme(.dark, for: .navigationBar)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button(isEditing ? "Cancel" : "Done") {
                        if isEditing {
                            isEditing = false
                        } else {
                            dismiss()
                        }
                    }
                    .foregroundStyle(Color.textSecondary)
                }
                ToolbarItem(placement: .confirmationAction) {
                    if isEditing {
                        Button {
                            saveChanges()
                        } label: {
                            Text(isSaving ? "Saving..." : "Save")
                                .font(.roundedHeadline)
                                .foregroundStyle(Color.accent)
                        }
                        .disabled(isSaving || selectedCategory.isEmpty)
                    } else {
                        Button {
                            isEditing = true
                        } label: {
                            Text("Edit")
                                .font(.roundedHeadline)
                                .foregroundStyle(Color.accent)
                        }
                    }
                }
            }
        }
    }

    // MARK: - Header card (editable fields)

    private var headerCard: some View {
        VStack(spacing: 0) {
            // Merchant name
            HStack {
                Text("Merchant")
                    .font(.roundedCaption)
                    .foregroundStyle(Color.textSecondary)
                    .frame(width: 72, alignment: .leading)
                Spacer()
                if isEditing {
                    TextField("Merchant name", text: $editedMerchant)
                        .font(.roundedBody)
                        .foregroundStyle(Color.textPrimary)
                        .multilineTextAlignment(.trailing)
                } else {
                    Text(editedMerchant)
                        .font(.roundedBody)
                        .foregroundStyle(Color.textPrimary)
                }
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 13)

            Divider().padding(.horizontal, 16)

            // Amount
            HStack {
                Text("Amount")
                    .font(.roundedCaption)
                    .foregroundStyle(Color.textSecondary)
                    .frame(width: 72, alignment: .leading)
                Spacer()
                if isEditing {
                    HStack(alignment: .firstTextBaseline, spacing: 3) {
                        Text("$")
                            .font(.rounded(.title3, weight: .bold))
                            .foregroundStyle(Color.accent)
                        TextField("0.00", text: $editedAmount)
                            .font(.rounded(.title3, weight: .bold))
                            .foregroundStyle(Color.accent)
                            .keyboardType(.decimalPad)
                            .multilineTextAlignment(.trailing)
                            .monospacedDigit()
                            .fixedSize()
                    }
                } else {
                    Text("$\(editedAmount)")
                        .font(.rounded(.title3, weight: .bold))
                        .foregroundStyle(Color.accent)
                        .monospacedDigit()
                }
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 13)

            Divider().padding(.horizontal, 16)

            // Date
            HStack {
                Text("Date")
                    .font(.roundedCaption)
                    .foregroundStyle(Color.textSecondary)
                    .frame(width: 72, alignment: .leading)
                Spacer()
                if isEditing {
                    DatePicker("", selection: $editedDate, displayedComponents: [.date])
                        .datePickerStyle(.compact)
                        .labelsHidden()
                        .tint(Color.accent)
                } else {
                    Text(editedDate, style: .date)
                        .font(.roundedBody)
                        .foregroundStyle(Color.textPrimary)
                }
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 13)

            // Source badge
            if transaction.source != nil {
                Divider().padding(.horizontal, 16)
                HStack {
                    Spacer()
                    sourceBadge
                }
                .padding(.horizontal, 16)
                .padding(.vertical, 10)
            }

            // Plaid category hint
            if let cat = transaction.categoryDetailed ?? transaction.categoryPrimary,
               !cat.isEmpty, transaction.source == nil || transaction.source == "plaid" {
                Divider().padding(.horizontal, 16)
                Text(cat.replacingOccurrences(of: "_", with: " ").capitalized)
                    .font(.roundedCaption)
                    .foregroundStyle(Color.textSecondary)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.horizontal, 16)
                    .padding(.vertical, 10)
            }

            // Voice notes
            if let notes = transaction.notes, !notes.isEmpty,
               transaction.source != "receipt" {
                Divider().padding(.horizontal, 16)
                Text(notes)
                    .font(.roundedBody)
                    .foregroundStyle(Color.textSecondary)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.horizontal, 16)
                    .padding(.vertical, 10)
            }
        }
        .background(Color.surface)
        .clipShape(RoundedRectangle(cornerRadius: 16))
        .padding(.horizontal)
    }

    private var sourceBadge: some View {
        let src = transaction.source ?? "plaid"
        let (icon, label, color): (String, String, Color) = {
            switch src {
            case "receipt": return ("receipt", "Receipt", Color.accent)
            case "voice":   return ("mic.fill", "Voice", Color.orange)
            case "manual":  return ("pencil", "Manual", Color.secondary)
            default:        return ("building.columns", "Plaid", Color.indigo)
            }
        }()
        return HStack(spacing: 5) {
            Image(systemName: icon)
                .font(.system(size: 12))
            Text(label)
                .font(.system(size: 13, weight: .semibold, design: .rounded))
        }
        .foregroundStyle(.white)
        .padding(.horizontal, 10)
        .padding(.vertical, 5)
        .background(color)
        .clipShape(Capsule())
    }

    // MARK: - Category picker

    @ViewBuilder
    private var categorySection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Category")
                .font(.roundedCaption)
                .foregroundStyle(Color.textSecondary)
                .padding(.horizontal)

            if isEditing {
                LazyVGrid(columns: [
                    GridItem(.flexible()),
                    GridItem(.flexible()),
                    GridItem(.flexible())
                ], spacing: 10) {
                    ForEach(CategoryManager.shared.categories) { cat in
                        Button {
                            selectedCategory = cat.displayName
                        } label: {
                            VStack(spacing: 6) {
                                Image(systemName: cat.icon)
                                    .font(.system(size: 20))
                                Text(cat.displayName)
                                    .font(.roundedCaption)
                            }
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 12)
                            .background(selectedCategory == cat.displayName ? categoryColor(for: cat.name).opacity(0.2) : Color.surface)
                            .foregroundStyle(selectedCategory == cat.displayName ? categoryColor(for: cat.name) : Color.textSecondary)
                            .clipShape(RoundedRectangle(cornerRadius: 12))
                            .overlay(
                                RoundedRectangle(cornerRadius: 12)
                                    .stroke(selectedCategory == cat.displayName ? categoryColor(for: cat.name) : Color.clear, lineWidth: 2)
                            )
                        }
                    }
                }
                .padding(.horizontal)
            } else if let cat = CategoryManager.shared.categories.first(where: { $0.displayName == selectedCategory }) {
                // Match the grid cell size: 1/3 width minus padding/spacing
                let columnWidth = (UIScreen.main.bounds.width - 32 - 20) / 3
                HStack {
                    VStack(spacing: 6) {
                        Image(systemName: cat.icon)
                            .font(.system(size: 20))
                        Text(cat.displayName)
                            .font(.roundedCaption)
                    }
                    .foregroundStyle(categoryColor(for: cat.name))
                    .frame(width: columnWidth)
                    .padding(.vertical, 12)
                    .background(categoryColor(for: cat.name).opacity(0.2))
                    .clipShape(RoundedRectangle(cornerRadius: 12))
                    .overlay(
                        RoundedRectangle(cornerRadius: 12)
                            .stroke(categoryColor(for: cat.name), lineWidth: 2)
                    )
                    Spacer()
                }
                .padding(.horizontal)
            }
        }
    }

    // MARK: - Delete Transaction Section

    private var deleteTransactionSection: some View {
        Button {
            showDeleteTxnConfirm = true
        } label: {
            Label("Delete Transaction", systemImage: "trash")
                .font(.roundedBody)
                .foregroundStyle(Color.danger)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 12)
                .background(Color.surface)
                .clipShape(RoundedRectangle(cornerRadius: 12))
        }
        .padding(.horizontal)
        .confirmationDialog("Delete this transaction?", isPresented: $showDeleteTxnConfirm, titleVisibility: .visible) {
            Button("Delete", role: .destructive) {
                Task {
                    try? await viewModel.deleteTransaction(transactionId: transaction.id)
                    dismiss()
                }
            }
            Button("Cancel", role: .cancel) {}
        } message: {
            Text("This cannot be undone.")
        }
    }

    // MARK: - Save

    private func saveChanges() {
        guard !isSaving, !selectedCategory.isEmpty else { return }
        isSaving = true
        Task {
            do {
                // Sync any item changes (edits, adds, deletes) first
                if localItemsModified {
                    let payload = localItems.map {
                        EditableReceiptItem(name: $0.name, price: $0.price, category: $0.category)
                    }
                    try await viewModel.addItemsToTransaction(
                        transactionId: transaction.id, items: payload, replace: true)
                }
                // Compute changed fields — only send overrides if actually different
                let newAmount = Double(editedAmount)
                let amountChanged = newAmount != nil && newAmount != transaction.amount
                let merchantChanged = editedMerchant != (transaction.merchantName ?? transaction.name)

                let dateFmt = DateFormatter()
                dateFmt.dateFormat = "yyyy-MM-dd"
                let newDateStr = dateFmt.string(from: editedDate)
                let dateChanged = newDateStr != transaction.date

                _ = try await viewModel.classifyTransactionForSheet(
                    transactionId: transaction.id,
                    subCategory: selectedCategory.lowercased(),
                    amount: amountChanged ? newAmount : nil,
                    merchantName: merchantChanged ? editedMerchant : nil,
                    date: dateChanged ? newDateStr : nil
                )
                isEditing = false
                dismiss()
            } catch {
                print("Failed to save: \(error)")
            }
            isSaving = false
        }
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
