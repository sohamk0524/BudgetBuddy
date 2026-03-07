//
//  ReceiptLineItemsView.swift
//  BudgetBuddy
//
//  Shows Claude Vision receipt analysis: editable merchant, date, global category,
//  and per-item category assignment with inline editing.
//

import SwiftUI

// MARK: - Editable item model

struct EditableReceiptItem: Identifiable {
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
}

// MARK: - Main View

struct ReceiptLineItemsView: View {
    let result: ReceiptAnalysisResult
    /// category: overall category chosen by user; items: edited line items
    let onConfirm: (_ category: String, _ items: [EditableReceiptItem], _ date: String, _ merchant: String) -> Void

    @State private var editableMerchant: String
    @State private var editableDate: Date
    @State private var items: [EditableReceiptItem]
    @State private var selectedCategory: String

    // Inline item category expansion
    @State private var expandedItemId: UUID?

    // Add item form
    @State private var showAddItemForm = false
    @State private var newItemName = ""
    @State private var newItemPrice = ""
    @State private var newItemCategory = "food"

    private let allCategories = ["food", "drink", "groceries", "transportation", "entertainment", "other"]

    init(result: ReceiptAnalysisResult,
         onConfirm: @escaping (_ category: String, _ items: [EditableReceiptItem], _ date: String, _ merchant: String) -> Void) {
        self.result = result
        self.onConfirm = onConfirm
        _editableMerchant = State(initialValue: result.merchant)
        let parsed = result.date.flatMap { DateFormatter.receiptISODate.date(from: $0) } ?? Date()
        _editableDate = State(initialValue: parsed)
        let editableItems = result.items.map { EditableReceiptItem(from: $0) }
        _items = State(initialValue: editableItems)
        // Pre-select dominant category from items
        var totals = [String: Double]()
        for item in editableItems { totals[item.category, default: 0] += item.price }
        let dominant = totals.max(by: { $0.value < $1.value })?.key ?? "food"
        _selectedCategory = State(initialValue: dominant)
    }

    // MARK: - Body

    var body: some View {
        VStack(spacing: 0) {
            ScrollView {
                VStack(spacing: 12) {
                    headerCard
                    categoryPicker
                    itemsSection
                }
                .padding(.vertical, 12)
            }
            confirmButton
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color.appBackground)
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
                TextField("Store name", text: $editableMerchant)
                    .font(.roundedBody)
                    .foregroundStyle(Color.textPrimary)
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 13)

            Divider().padding(.horizontal, 16)

            // Total row
            HStack {
                Text("Total")
                    .font(.roundedCaption)
                    .foregroundStyle(Color.textSecondary)
                    .frame(width: 52, alignment: .leading)
                Spacer()
                Text("$\(result.total, specifier: "%.2f")")
                    .font(.rounded(.title3, weight: .bold))
                    .foregroundStyle(Color.accent)
                    .monospacedDigit()
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 13)

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

    // MARK: - Items Section

    private var itemsSection: some View {
        VStack(alignment: .leading, spacing: 8) {
            // Header row + Add Item toggle
            HStack {
                Text("Items")
                    .font(.roundedCaption)
                    .foregroundStyle(Color.textSecondary)
                Spacer()
                Button {
                    withAnimation(.spring(duration: 0.25)) {
                        showAddItemForm.toggle()
                        if showAddItemForm {
                            newItemName = ""
                            newItemPrice = ""
                            newItemCategory = "food"
                            expandedItemId = nil
                        }
                    }
                } label: {
                    Label(showAddItemForm ? "Cancel" : "Add Item",
                          systemImage: showAddItemForm ? "xmark" : "plus")
                        .font(.roundedCaption)
                        .foregroundStyle(Color.accent)
                }
            }
            .padding(.horizontal)

            // Add item form appears DIRECTLY below the header row
            if showAddItemForm {
                addItemForm
            }

            // Item rows
            ForEach($items) { $item in
                itemRow(item: $item)
            }
        }
    }

    // MARK: - Item Row (with inline category expansion)

    private func itemRow(item: Binding<EditableReceiptItem>) -> some View {
        VStack(spacing: 0) {
            HStack(spacing: 10) {
                TextField("Item name", text: item.name)
                    .font(.roundedBody)
                    .foregroundStyle(Color.textPrimary)
                    .frame(maxWidth: .infinity, alignment: .leading)

                TextField("0.00", value: item.price,
                          format: .number.precision(.fractionLength(2)))
                    .font(.roundedBody.monospacedDigit())
                    .foregroundStyle(Color.textPrimary)
                    .multilineTextAlignment(.trailing)
                    .keyboardType(.decimalPad)
                    .frame(width: 60)

                // Tappable badge — expands inline picker below
                Button {
                    withAnimation(.spring(duration: 0.2)) {
                        expandedItemId = expandedItemId == item.wrappedValue.id
                            ? nil : item.wrappedValue.id
                    }
                } label: {
                    HStack(spacing: 3) {
                        Text(item.wrappedValue.category.capitalized)
                            .font(.system(size: 10, weight: .semibold, design: .rounded))
                        Image(systemName: "chevron.down")
                            .font(.system(size: 8, weight: .bold))
                            .rotationEffect(.degrees(
                                expandedItemId == item.wrappedValue.id ? 180 : 0))
                    }
                    .foregroundStyle(.white)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 4)
                    .background(categoryColor(for: item.wrappedValue.category))
                    .clipShape(Capsule())
                }
                .buttonStyle(.plain)
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 10)

            // Inline category chips expand right below this row
            if expandedItemId == item.wrappedValue.id {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 6) {
                        ForEach(allCategories, id: \.self) { cat in
                            Button {
                                item.wrappedValue.category = cat
                                withAnimation { expandedItemId = nil }
                            } label: {
                                Text(cat.capitalized)
                                    .font(.system(size: 11, weight: .semibold, design: .rounded))
                                    .foregroundStyle(
                                        item.wrappedValue.category == cat ? .white : Color.textSecondary)
                                    .padding(.horizontal, 12)
                                    .padding(.vertical, 6)
                                    .background(
                                        item.wrappedValue.category == cat
                                            ? categoryColor(for: cat)
                                            : Color.appBackground)
                                    .clipShape(Capsule())
                            }
                            .buttonStyle(.plain)
                        }
                    }
                    .padding(.horizontal, 14)
                    .padding(.bottom, 8)
                }
                .transition(.opacity.combined(with: .move(edge: .top)))
            }
        }
        .background(Color.surface)
        .clipShape(RoundedRectangle(cornerRadius: 12))
        .padding(.horizontal)
        .animation(.spring(duration: 0.2), value: expandedItemId)
    }

    // MARK: - Add Item Form

    private var addItemForm: some View {
        VStack(spacing: 10) {
            HStack(spacing: 10) {
                TextField("Item name", text: $newItemName)
                    .font(.roundedBody)
                    .foregroundStyle(Color.textPrimary)
                    .frame(maxWidth: .infinity)
                TextField("0.00", text: $newItemPrice)
                    .font(.roundedBody.monospacedDigit())
                    .foregroundStyle(Color.textPrimary)
                    .multilineTextAlignment(.trailing)
                    .keyboardType(.decimalPad)
                    .frame(width: 60)
            }

            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 6) {
                    ForEach(allCategories, id: \.self) { cat in
                        Button { newItemCategory = cat } label: {
                            Text(cat.capitalized)
                                .font(.system(size: 11, weight: .semibold, design: .rounded))
                                .foregroundStyle(newItemCategory == cat ? .white : Color.textSecondary)
                                .padding(.horizontal, 12)
                                .padding(.vertical, 6)
                                .background(newItemCategory == cat
                                    ? categoryColor(for: cat) : Color.appBackground)
                                .clipShape(Capsule())
                        }
                        .buttonStyle(.plain)
                    }
                }
            }

            Button {
                let price = Double(newItemPrice) ?? 0
                guard !newItemName.trimmingCharacters(in: .whitespaces).isEmpty else { return }
                withAnimation {
                    items.append(EditableReceiptItem(
                        name: newItemName, price: price, category: newItemCategory))
                    newItemName = ""
                    newItemPrice = ""
                    showAddItemForm = false
                }
            } label: {
                Text("Add Item")
                    .font(.roundedBody).fontWeight(.semibold)
                    .foregroundStyle(.white)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 10)
                    .background(newItemName.trimmingCharacters(in: .whitespaces).isEmpty
                        ? Color.accent.opacity(0.4) : Color.accent)
                    .clipShape(RoundedRectangle(cornerRadius: 10))
            }
            .disabled(newItemName.trimmingCharacters(in: .whitespaces).isEmpty)
        }
        .padding(14)
        .background(Color.surface)
        .clipShape(RoundedRectangle(cornerRadius: 14))
        .padding(.horizontal)
        .transition(.opacity.combined(with: .move(edge: .top)))
    }

    // MARK: - Confirm Button

    private var confirmButton: some View {
        Button {
            let dateStr = DateFormatter.receiptISODate.string(from: editableDate)
            onConfirm(selectedCategory, items, dateStr, editableMerchant)
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
