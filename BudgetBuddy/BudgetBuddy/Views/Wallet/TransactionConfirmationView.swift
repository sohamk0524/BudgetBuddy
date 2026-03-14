//
//  TransactionConfirmationView.swift
//  BudgetBuddy
//
//  Editable form for logging a transaction manually or by voice.
//  Layout mirrors ReceiptLineItemsView for visual consistency.
//

import SwiftUI

@MainActor
struct TransactionConfirmationView: View {
    @Bindable var viewModel: VoiceTransactionViewModel
    @Environment(\.dismiss) private var dismiss

    // Local editable state
    @State private var amountText: String = ""
    @State private var selectedCategory: String = ""
    @State private var store: String = ""
    @State private var date: Date = Date()
    @State private var items: [EditableReceiptItem] = []
    @State private var showCategoryError: Bool = false
    @State private var showDiscardConfirm: Bool = false

    private var categories: [String] {
        CategoryManager.shared.categories.map { $0.displayName }
    }

    private var itemsTotal: Double { items.reduce(0) { $0 + $1.price } }

    // MARK: - Computed

    private var isAmountValid: Bool {
        guard let amount = Double(amountText), amount > 0 else { return false }
        return true
    }

    private var navTitle: String {
        viewModel.showCounter
            ? "Transaction \(viewModel.currentIndex + 1) of \(viewModel.totalCount)"
            : "Log Transaction"
    }

    private var confirmButtonLabel: String {
        guard viewModel.showCounter else { return "Confirm & Save" }
        return viewModel.isLastTransaction ? "Save & Finish" : "Save & Next"
    }

    // MARK: - Body

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                ScrollView {
                    VStack(spacing: 12) {
                        // Transcription context
                        if !viewModel.transcribedText.isEmpty {
                            transcriptionCard
                        }

                        headerCard
                        categoryPicker
                        TransactionItemsSection(items: $items, onAdd: { _ in
                            let newTotal = itemsTotal
                            if let current = Double(amountText), newTotal > current {
                                amountText = String(format: "%.2f", newTotal)
                            } else if amountText.isEmpty || Double(amountText) == nil {
                                amountText = String(format: "%.2f", newTotal)
                            }
                        })

                        if viewModel.showCounter {
                            discardButton
                        }
                    }
                    .padding(.vertical, 12)
                }
                .background(Color.appBackground)

                confirmButton
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .background(Color.appBackground)
            .navigationTitle(navTitle)
            .navigationBarTitleDisplayMode(.inline)
            .toolbarBackground(Color.appBackground, for: .navigationBar)
            .toolbarColorScheme(.dark, for: .navigationBar)
            .toolbar {
                if viewModel.canGoBack {
                    ToolbarItem(placement: .topBarLeading) {
                        Button {
                            saveLocalStateToViewModel()
                            viewModel.goBack()
                        } label: {
                            HStack(spacing: 4) {
                                Image(systemName: "chevron.left")
                                    .font(.system(size: 14, weight: .semibold))
                                Text("Back")
                                    .font(.roundedBody)
                            }
                            .foregroundStyle(Color.accent)
                        }
                    }
                }

                ToolbarItem(placement: .topBarTrailing) {
                    Button {
                        viewModel.reset()
                        dismiss()
                    } label: {
                        Image(systemName: "xmark.circle.fill")
                            .foregroundStyle(Color.textSecondary)
                            .font(.system(size: 20))
                    }
                }
            }
        }
        .onAppear { populateFromViewModel() }
        .onChange(of: viewModel.currentIndex) { _, _ in populateFromViewModel() }
    }

    // MARK: - Transcription Card

    private var transcriptionCard: some View {
        HStack(alignment: .top, spacing: 8) {
            Image(systemName: "quote.opening")
                .foregroundStyle(Color.accent)
                .font(.system(size: 13))
                .padding(.top, 2)
            Text(viewModel.transcribedText)
                .font(.roundedCaption)
                .foregroundStyle(Color.textSecondary)
                .italic()
                .fixedSize(horizontal: false, vertical: true)
            Spacer()
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 12)
        .background(Color.surface)
        .clipShape(RoundedRectangle(cornerRadius: 14))
        .padding(.horizontal)
    }

    // MARK: - Header Card (Store / Amount / Date rows)

    private var headerCard: some View {
        VStack(spacing: 0) {
            // Store
            HStack {
                Text("Store")
                    .font(.roundedCaption)
                    .foregroundStyle(Color.textSecondary)
                    .frame(width: 68, alignment: .leading)
                Spacer()
                TextField("Store name", text: $store)
                    .font(.roundedBody)
                    .foregroundStyle(Color.textPrimary)
                    .multilineTextAlignment(.trailing)
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 13)

            Divider().padding(.horizontal, 16)

            // Amount
            HStack {
                Text("Amount")
                    .font(.roundedCaption)
                    .foregroundStyle(Color.textSecondary)
                    .frame(width: 68, alignment: .leading)
                Spacer()
                HStack(alignment: .firstTextBaseline, spacing: 3) {
                    Text("$")
                        .font(.rounded(.title3, weight: .bold))
                        .foregroundStyle(Color.accent)
                    TextField("0.00", text: $amountText)
                        .font(.rounded(.title3, weight: .bold))
                        .foregroundStyle(Color.accent)
                        .keyboardType(.decimalPad)
                        .multilineTextAlignment(.trailing)
                        .monospacedDigit()
                        .fixedSize()
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
                    .frame(width: 68, alignment: .leading)
                Spacer()
                DatePicker("", selection: $date, displayedComponents: [.date])
                    .datePickerStyle(.compact)
                    .labelsHidden()
                    .tint(Color.accent)
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 13)
        }
        .background(Color.surface)
        .clipShape(RoundedRectangle(cornerRadius: 16))
        .padding(.horizontal)
    }

    // MARK: - Category Picker

    private var categoryPicker: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 6) {
                Text("Category")
                    .font(.roundedCaption)
                    .foregroundStyle(showCategoryError && selectedCategory.isEmpty
                                     ? Color.danger : Color.textSecondary)
                if showCategoryError && selectedCategory.isEmpty {
                    Text("— required")
                        .font(.roundedCaption)
                        .foregroundStyle(Color.danger)
                }
            }
            .padding(.horizontal)

            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 8) {
                    ForEach(categories, id: \.self) { cat in
                        Button {
                            selectedCategory = cat
                            showCategoryError = false
                        } label: {
                            Text(cat)
                                .font(.roundedCaption)
                                .foregroundStyle(selectedCategory == cat ? .white : Color.textPrimary)
                                .padding(.horizontal, 16)
                                .padding(.vertical, 8)
                                .background(selectedCategory == cat
                                    ? categoryColor(for: cat)
                                    : Color.surface)
                                .clipShape(Capsule())
                                .overlay(
                                    Capsule()
                                        .stroke(showCategoryError && selectedCategory.isEmpty
                                                ? Color.danger.opacity(0.5) : Color.clear,
                                                lineWidth: 1)
                                )
                        }
                        .buttonStyle(.plain)
                    }
                }
                .padding(.horizontal)
            }
        }
        .padding(.vertical, 4)
    }

    // MARK: - Discard Button

    private var discardButton: some View {
        Button {
            showDiscardConfirm = true
        } label: {
            Label("Discard This Transaction", systemImage: "trash")
                .font(.roundedCaption)
                .foregroundStyle(Color.danger)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 12)
                .background(Color.danger.opacity(0.08))
                .clipShape(RoundedRectangle(cornerRadius: 12))
        }
        .padding(.horizontal)
        .confirmationDialog(
            "Discard this transaction?",
            isPresented: $showDiscardConfirm,
            titleVisibility: .visible
        ) {
            Button("Discard", role: .destructive) {
                Task { await viewModel.discardCurrentTransaction() }
            }
            Button("Cancel", role: .cancel) {}
        } message: {
            Text("This transaction will be removed and cannot be recovered.")
        }
    }

    // MARK: - Confirm Button (pinned bottom)

    private var confirmButton: some View {
        Button {
            confirmTransaction()
        } label: {
            HStack(spacing: 8) {
                if case .saving = viewModel.state {
                    ProgressView().tint(.white)
                } else {
                    Image(systemName: "checkmark.circle.fill")
                }
                Text(confirmButtonLabel)
                    .font(.roundedHeadline).fontWeight(.semibold)
            }
            .foregroundStyle(.white)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 14)
            .background(isAmountValid ? Color.accent : Color.accent.opacity(0.3))
            .clipShape(RoundedRectangle(cornerRadius: 14))
        }
        .disabled(!isAmountValid || viewModel.state == .saving)
        .padding(.horizontal)
        .padding(.vertical, 12)
        .background(Color.surface)
    }

    // MARK: - Helpers

    private func populateFromViewModel() {
        showCategoryError = false
        if let amount = viewModel.transaction.amount {
            amountText = String(format: "%.2f", amount)
        } else {
            amountText = ""
        }
        if let category = viewModel.transaction.category,
           let match = categories.first(where: { $0.caseInsensitiveCompare(category) == .orderedSame }) {
            selectedCategory = match
        } else {
            selectedCategory = ""
        }
        store = viewModel.transaction.store ?? ""
        date = viewModel.transaction.date
        items = viewModel.transaction.items
    }

    private func saveLocalStateToViewModel() {
        viewModel.transaction.amount = Double(amountText)
        viewModel.transaction.category = selectedCategory.isEmpty ? nil : selectedCategory
        viewModel.transaction.store = store.isEmpty ? nil : store
        viewModel.transaction.date = date
        viewModel.transaction.items = items
    }

    private func confirmTransaction() {
        guard !selectedCategory.isEmpty else {
            showCategoryError = true
            return
        }
        saveLocalStateToViewModel()
        Task { await viewModel.saveTransaction() }
    }
}
