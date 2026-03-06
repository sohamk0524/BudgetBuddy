//
//  ReceiptLineItemsView.swift
//  BudgetBuddy
//
//  Shows Claude Vision receipt analysis: merchant, total, line items,
//  and a category picker for the whole receipt.
//

import SwiftUI

struct ReceiptLineItemsView: View {
    let result: ReceiptAnalysisResult
    /// Called on confirm with category, date, and merchant.
    let onConfirm: (_ category: String, _ date: String, _ merchant: String) -> Void

    @State private var editableMerchant: String
    @State private var editableDate: Date
    @State private var selectedCategory: String = "Food"

    private let categories = ["Food", "Drink", "Transportation", "Entertainment", "Other"]

    init(result: ReceiptAnalysisResult, onConfirm: @escaping (_ category: String, _ date: String, _ merchant: String) -> Void) {
        self.result = result
        self.onConfirm = onConfirm
        _editableMerchant = State(initialValue: result.merchant)
        let parsed = result.date.flatMap { DateFormatter.isoDate.date(from: $0) } ?? Date()
        _editableDate = State(initialValue: parsed)
    }

    // MARK: - Body

    var body: some View {
        VStack(spacing: 0) {
            // Header card
            VStack(alignment: .leading, spacing: 12) {
                HStack(alignment: .center) {
                    TextField("Store name", text: $editableMerchant)
                        .font(.roundedHeadline)
                        .foregroundStyle(Color.textPrimary)
                    Spacer()
                    Text("$\(result.total, specifier: "%.2f")")
                        .font(.rounded(.title2, weight: .bold))
                        .foregroundStyle(Color.accent)
                        .monospacedDigit()
                }

                HStack {
                    Text("Date")
                        .font(.roundedCaption)
                        .foregroundStyle(Color.textSecondary)
                    Spacer()
                    DatePicker("", selection: $editableDate, displayedComponents: [.date])
                        .datePickerStyle(.compact)
                        .labelsHidden()
                        .tint(Color.accent)
                }
            }
            .padding(16)
            .background(Color.surface)
            .clipShape(RoundedRectangle(cornerRadius: 16))
            .padding(.horizontal)
            .padding(.top, 12)

            // Category picker
            VStack(alignment: .leading, spacing: 10) {
                Text("Category")
                    .font(.roundedCaption)
                    .foregroundStyle(Color.textSecondary)
                    .padding(.horizontal)

                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 8) {
                        ForEach(categories, id: \.self) { cat in
                            Button {
                                selectedCategory = cat
                            } label: {
                                Text(cat)
                                    .font(.roundedCaption)
                                    .foregroundStyle(selectedCategory == cat ? Color.appBackground : Color.textPrimary)
                                    .padding(.horizontal, 16)
                                    .padding(.vertical, 8)
                                    .background(selectedCategory == cat ? Color.accent : Color.surface)
                                    .clipShape(Capsule())
                            }
                        }
                    }
                    .padding(.horizontal)
                }
            }
            .padding(.vertical, 12)

            // Line items — display only
            ScrollView {
                LazyVStack(spacing: 8) {
                    ForEach(Array(result.items.enumerated()), id: \.offset) { _, item in
                        HStack(spacing: 12) {
                            Text(item.name)
                                .font(.roundedBody)
                                .foregroundStyle(Color.textPrimary)
                                .lineLimit(2)
                                .multilineTextAlignment(.leading)
                                .frame(maxWidth: .infinity, alignment: .leading)

                            Text("$\(item.price, specifier: "%.2f")")
                                .font(.roundedBody)
                                .fontWeight(.medium)
                                .foregroundStyle(Color.textPrimary)
                                .monospacedDigit()
                        }
                        .padding(.horizontal, 16)
                        .padding(.vertical, 10)
                        .background(Color.surface)
                        .clipShape(RoundedRectangle(cornerRadius: 12))
                        .padding(.horizontal)
                    }
                }
                .padding(.bottom, 12)
            }

            // Confirm button
            Button {
                let dateStr = DateFormatter.isoDate.string(from: editableDate)
                onConfirm(selectedCategory.lowercased(), dateStr, editableMerchant)
            } label: {
                Text("Confirm & Save")
                    .font(.roundedHeadline)
                    .fontWeight(.semibold)
                    .foregroundStyle(.white)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 14)
                    .background(Color.accent)
                    .clipShape(RoundedRectangle(cornerRadius: 14))
            }
            .padding(.horizontal)
            .padding(.vertical, 12)
            .background(Color.surface)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color.appBackground)
    }
}

// MARK: - DateFormatter helper

private extension DateFormatter {
    static let isoDate: DateFormatter = {
        let f = DateFormatter()
        f.dateFormat = "yyyy-MM-dd"
        return f
    }()
}
