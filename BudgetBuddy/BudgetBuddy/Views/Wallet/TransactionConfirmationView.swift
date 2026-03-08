//
//  TransactionConfirmationView.swift
//  BudgetBuddy
//
//  Editable form for logging a transaction manually or by voice
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
    private let categories = ["Food", "Drink", "Groceries", "Transportation", "Entertainment", "Other"]

    private var itemsTotal: Double { items.reduce(0) { $0 + $1.price } }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 24) {
                    // Transcription context (shown after voice input)
                    if !viewModel.transcribedText.isEmpty {
                        HStack {
                            Image(systemName: "quote.opening")
                                .foregroundStyle(Color.accent)
                                .font(.system(size: 14))
                            Text(viewModel.transcribedText)
                                .font(.roundedCaption)
                                .foregroundStyle(Color.textSecondary)
                                .italic()
                            Spacer()
                        }
                        .padding()
                        .background(Color.surface)
                        .clipShape(RoundedRectangle(cornerRadius: 12))
                    }

                    // MARK: - Manual Form

                    // Amount
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Amount")
                            .font(.roundedCaption)
                            .foregroundStyle(Color.textSecondary)
                        HStack(alignment: .firstTextBaseline, spacing: 4) {
                            Text("$")
                                .font(.system(size: 36, weight: .bold, design: .rounded))
                                .foregroundStyle(Color.accent)
                            TextField("0.00", text: $amountText)
                                .font(.system(size: 36, weight: .bold, design: .rounded))
                                .foregroundStyle(Color.textPrimary)
                                .keyboardType(.decimalPad)
                        }
                    }
                    .padding()
                    .background(Color.surface)
                    .clipShape(RoundedRectangle(cornerRadius: 12))

                    // Category
                    VStack(alignment: .leading, spacing: 12) {
                        Text("Category")
                            .font(.roundedCaption)
                            .foregroundStyle(Color.textSecondary)

                        ScrollView(.horizontal, showsIndicators: false) {
                            HStack(spacing: 8) {
                                ForEach(categories, id: \.self) { category in
                                    Button {
                                        selectedCategory = category
                                    } label: {
                                        Text(category)
                                            .font(.roundedCaption)
                                            .foregroundStyle(selectedCategory == category ? .white : Color.textPrimary)
                                            .padding(.horizontal, 16)
                                            .padding(.vertical, 8)
                                            .background(selectedCategory == category
                                                ? categoryColor(for: category)
                                                : Color.surface)
                                            .clipShape(Capsule())
                                    }
                                }
                            }
                        }
                    }

                    // Store
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Store")
                            .font(.roundedCaption)
                            .foregroundStyle(Color.textSecondary)
                        TextField("Store name", text: $store)
                            .font(.roundedBody)
                            .foregroundStyle(Color.textPrimary)
                            .padding(12)
                            .background(Color.surface)
                            .clipShape(RoundedRectangle(cornerRadius: 10))
                    }

                    // Date
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Date")
                            .font(.roundedCaption)
                            .foregroundStyle(Color.textSecondary)
                        DatePicker("", selection: $date, displayedComponents: [.date])
                            .datePickerStyle(.compact)
                            .labelsHidden()
                            .tint(Color.accent)
                    }

                    // Items
                    TransactionItemsSection(items: $items, onAdd: { item in
                        let newTotal = itemsTotal
                        if let current = Double(amountText), newTotal > current {
                            amountText = String(format: "%.2f", newTotal)
                        } else if amountText.isEmpty || Double(amountText) == nil {
                            amountText = String(format: "%.2f", newTotal)
                        }
                    })

                    // Confirm button
                    Button {
                        confirmTransaction()
                    } label: {
                        HStack(spacing: 8) {
                            Image(systemName: "checkmark.circle.fill")
                            Text("Confirm Transaction")
                                .font(.roundedHeadline)
                        }
                        .foregroundStyle(Color.appBackground)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 16)
                        .background(isAmountValid ? Color.accent : Color.accent.opacity(0.3))
                        .clipShape(RoundedRectangle(cornerRadius: 14))
                    }
                    .disabled(!isAmountValid)

                    if case .saving = viewModel.state {
                        ProgressView()
                            .tint(Color.accent)
                    }
                }
                .padding()
            }
            .background(Color.appBackground)
            .navigationTitle("Log Transaction")
            .navigationBarTitleDisplayMode(.inline)
            .toolbarBackground(Color.appBackground, for: .navigationBar)
            .toolbarColorScheme(.dark, for: .navigationBar)
            .toolbar {
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
        .onAppear {
            populateFromViewModel()
        }
    }

    // MARK: - Helpers

    private var isAmountValid: Bool {
        guard let amount = Double(amountText), amount > 0 else { return false }
        return true
    }

    private func populateFromViewModel() {
        if let amount = viewModel.transaction.amount {
            amountText = String(format: "%.2f", amount)
        }
        if let category = viewModel.transaction.category, categories.contains(category) {
            selectedCategory = category
        }
        store = viewModel.transaction.store ?? ""
        date = viewModel.transaction.date
        items = viewModel.transaction.items
    }

    private func saveLocalStateToViewModel() {
        viewModel.transaction.amount = Double(amountText)
        viewModel.transaction.category = selectedCategory.isEmpty ? "Other" : selectedCategory
        viewModel.transaction.store = store.isEmpty ? nil : store
        viewModel.transaction.date = date
        viewModel.transaction.items = items
    }

    private func confirmTransaction() {
        saveLocalStateToViewModel()

        Task {
            await viewModel.saveTransaction()
        }
    }
}
