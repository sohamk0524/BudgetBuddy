//
//  ReceiptLineItemsView.swift
//  BudgetBuddy
//
//  Shows Claude Vision receipt analysis: editable merchant, date, global category,
//  and per-item category assignment with inline editing.
//

import SwiftUI

// MARK: - Editable item model

struct EditableReceiptItem: Identifiable, Codable, Equatable {
    let id: UUID
    var name: String
    var price: Double
    var category: String   // "food", "drink", "groceries", "transportation", "entertainment", "other"

    init(from item: ReceiptLineItem) {
        self.id = item.id
        self.name = item.name
        self.price = item.price
        self.category = item.category
    }

    init(name: String = "", price: Double = 0, category: String = "food") {
        self.id = UUID()
        self.name = name
        self.price = price
        self.category = category
    }

    func toReceiptLineItem() -> ReceiptLineItem {
        ReceiptLineItem(name: name, price: price, category: category)
    }

    var isDiscount: Bool { price < 0 }
}

// MARK: - Main View

struct ReceiptLineItemsView: View {
    let result: ReceiptAnalysisResult
    /// category: overall category chosen by user; items: edited line items
    let onConfirm: (_ category: String, _ items: [EditableReceiptItem], _ date: String, _ merchant: String) -> Void

    @State private var editableMerchant: String
    @State private var editableDate: Date
    @State private var allItems: [EditableReceiptItem]   // positive = regular, negative = discounts
    @State private var editableTotal: Double
    @State private var totalIsAutoComputed: Bool
    @State private var selectedCategory: String

    private let allCategories = ["food", "drink", "groceries", "transportation", "entertainment", "other"]

    init(result: ReceiptAnalysisResult,
         onConfirm: @escaping (_ category: String, _ items: [EditableReceiptItem], _ date: String, _ merchant: String) -> Void) {
        self.result = result
        self.onConfirm = onConfirm
        _editableMerchant = State(initialValue: result.merchant)
        let parsed = result.date.flatMap { DateFormatter.receiptISODate.date(from: $0) } ?? Date()
        _editableDate = State(initialValue: parsed)

        let nonZero = result.items.map { EditableReceiptItem(from: $0) }.filter { $0.price != 0 }
        _allItems = State(initialValue: nonZero)
        _editableTotal = State(initialValue: result.total)
        _totalIsAutoComputed = State(initialValue: true)

        // Pre-select dominant category from positive-price items
        var totals = [String: Double]()
        for item in nonZero where item.price > 0 { totals[item.category, default: 0] += item.price }
        let dominant = totals.max(by: { $0.value < $1.value })?.key ?? "food"
        _selectedCategory = State(initialValue: dominant)
    }

    // MARK: - Computed helpers

    private var itemsSum: Double {
        allItems.reduce(0) { $0 + $1.price }
    }

    private var taxAmount: Double { max(0, editableTotal - itemsSum) }

    // MARK: - Body

    var body: some View {
        VStack(spacing: 0) {
            ScrollView {
                VStack(spacing: 12) {
                    headerCard
                    categoryPicker
                    TransactionItemsSection(items: $allItems, editable: true)
                }
                .padding(.vertical, 12)
            }
            confirmButton
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color.appBackground)
        .onChange(of: itemsSum) { _, _ in
            if totalIsAutoComputed { editableTotal = itemsSum }
        }
    }

    // MARK: - Header Card (3 separate rows)

    private var headerCard: some View {
        VStack(spacing: 0) {
            // Merchant row
            HStack {
                Text("Store")
                    .font(.roundedCaption)
                    .foregroundStyle(Color.textSecondary)
                    .frame(width: 52, alignment: .leading)
                Spacer()
                TextField("Store name", text: $editableMerchant)
                    .font(.roundedBody)
                    .foregroundStyle(Color.textPrimary)
                    .multilineTextAlignment(.trailing)
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 13)

            Divider().padding(.horizontal, 16)

            // Total row (auto-computed or user-overridden)
            HStack {
                Text("Total")
                    .font(.roundedCaption)
                    .foregroundStyle(Color.textSecondary)
                    .frame(width: 52, alignment: .leading)
                Spacer()
                TextField("0.00", value: Binding(
                    get: { editableTotal },
                    set: { editableTotal = $0; totalIsAutoComputed = false }
                ), format: .number.precision(.fractionLength(2)))
                    .font(.rounded(.title3, weight: .bold))
                    .foregroundStyle(Color.accent)
                    .multilineTextAlignment(.trailing)
                    .keyboardType(.decimalPad)
                    .monospacedDigit()
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 13)

            // Tax row — shown when total > itemsSum
            if taxAmount > 0.005 {
                Divider().padding(.horizontal, 16)
                HStack {
                    Text("Tax / Fees")
                        .font(.roundedCaption)
                        .foregroundStyle(Color.textSecondary)
                        .frame(width: 52, alignment: .leading)
                    Spacer()
                    Text("$\(taxAmount, specifier: "%.2f")")
                        .font(.roundedBody)
                        .foregroundStyle(Color.textSecondary)
                        .monospacedDigit()
                }
                .padding(.horizontal, 16)
                .padding(.vertical, 13)
            }

            Divider().padding(.horizontal, 16)

            // Date row
            HStack {
                Text("Date")
                    .font(.roundedCaption)
                    .foregroundStyle(Color.textSecondary)
                    .frame(width: 52, alignment: .leading)
                Spacer()
                DatePicker("", selection: $editableDate, displayedComponents: [.date])
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

    // MARK: - Global Category Picker

    private var categoryPicker: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Category")
                .font(.roundedCaption)
                .foregroundStyle(Color.textSecondary)
                .padding(.horizontal)

            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 8) {
                    ForEach(allCategories, id: \.self) { cat in
                        Button {
                            selectedCategory = cat
                        } label: {
                            Text(cat.capitalized)
                                .font(.roundedCaption)
                                .foregroundStyle(selectedCategory == cat ? .white : Color.textPrimary)
                                .padding(.horizontal, 16)
                                .padding(.vertical, 8)
                                .background(selectedCategory == cat
                                    ? categoryColor(for: cat)
                                    : Color.surface)
                                .clipShape(Capsule())
                        }
                        .buttonStyle(.plain)
                    }
                }
                .padding(.horizontal)
            }
        }
        .padding(.vertical, 4)
    }

    // MARK: - Confirm Button

    private var confirmButton: some View {
        Button {
            let dateStr = DateFormatter.receiptISODate.string(from: editableDate)
            onConfirm(selectedCategory, allItems, dateStr, editableMerchant)
        } label: {
            Text("Confirm & Save")
                .font(.roundedHeadline).fontWeight(.semibold)
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
}

// MARK: - DateFormatter helper

extension DateFormatter {
    static let receiptISODate: DateFormatter = {
        let f = DateFormatter()
        f.dateFormat = "yyyy-MM-dd"
        return f
    }()
}
