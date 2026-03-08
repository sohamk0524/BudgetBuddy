//
//  TransactionItemsSection.swift
//  BudgetBuddy
//
//  Shared items list used across receipt scan, voice/manual entry, and transaction detail.
//  Tap any row to expand its inline category picker and delete button.
//

import SwiftUI

struct TransactionItemsSection: View {
    @Binding var items: [EditableReceiptItem]
    /// When true, item rows show editable TextFields for name and price (receipt scan review).
    var editable: Bool = false
    /// Optional callback fired after a new item is appended (e.g. to auto-adjust a total).
    var onAdd: ((EditableReceiptItem) -> Void)? = nil

    @State private var isEditMode = false
    @State private var editingItemId: UUID? = nil
    @State private var showAddForm = false
    @State private var newName = ""
    @State private var newPrice = ""
    @State private var newCategory = "food"

    private let allCategories = ["food", "drink", "groceries", "transportation", "entertainment", "other"]

    private var regularItems: [EditableReceiptItem] { items.filter { $0.price > 0 } }
    private var discountItems: [EditableReceiptItem] { items.filter { $0.price < 0 } }

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            // Header
            HStack {
                Text("Items")
                    .font(.roundedCaption)
                    .foregroundStyle(Color.textSecondary)
                Spacer()
                if isEditMode {
                    Button {
                        withAnimation(.spring(duration: 0.25)) {
                            showAddForm.toggle()
                            if showAddForm {
                                newName = ""; newPrice = ""; newCategory = "food"
                                editingItemId = nil
                            }
                        }
                    } label: {
                        Label(showAddForm ? "Cancel" : "Add Item",
                              systemImage: showAddForm ? "xmark" : "plus")
                            .font(.roundedCaption)
                            .foregroundStyle(Color.accent)
                    }
                }
                Button {
                    withAnimation(.spring(duration: 0.25)) {
                        isEditMode.toggle()
                        if !isEditMode {
                            editingItemId = nil
                            showAddForm = false
                        }
                    }
                } label: {
                    Label(isEditMode ? "Done" : "Edit",
                          systemImage: isEditMode ? "checkmark" : "pencil")
                        .font(.roundedCaption)
                        .fontWeight(.semibold)
                        .foregroundStyle(isEditMode ? .white : Color.textSecondary)
                        .padding(.horizontal, 12)
                        .padding(.vertical, 5)
                        .background(isEditMode ? Color.accent : Color.surface)
                        .clipShape(Capsule())
                }
                .padding(.leading, 4)
            }
            .padding(.horizontal)

            if showAddForm {
                addItemForm
            }

            if !regularItems.isEmpty {
                VStack(spacing: 6) {
                    ForEach(regularItems) { item in
                        itemRow(item, isDiscount: false)
                    }
                }
            }

            if !discountItems.isEmpty {
                VStack(alignment: .leading, spacing: 6) {
                    Text("Discounts")
                        .font(.roundedCaption)
                        .foregroundStyle(.green)
                        .padding(.horizontal)
                    ForEach(discountItems) { item in
                        itemRow(item, isDiscount: true)
                    }
                }
            }
        }
    }

    // MARK: - Item Row

    @ViewBuilder
    private func itemRow(_ item: EditableReceiptItem, isDiscount: Bool) -> some View {
        let isExpanded = editingItemId == item.id
        // Read live category from the binding (not stale copy from ForEach)
        let liveCat = (items.first(where: { $0.id == item.id })?.category ?? item.category).lowercased()

        VStack(spacing: 0) {
            HStack(spacing: 10) {
                // Name
                if editable {
                    TextField("Item name", text: nameBinding(item))
                        .font(.roundedBody)
                        .foregroundStyle(Color.textPrimary)
                        .frame(maxWidth: .infinity, alignment: .leading)
                } else {
                    Text(item.name)
                        .font(.roundedBody)
                        .foregroundStyle(Color.textPrimary)
                        .frame(maxWidth: .infinity, alignment: .leading)
                }

                // Price
                if editable {
                    if isDiscount {
                        HStack(spacing: 2) {
                            Text("−")
                                .font(.roundedBody.monospacedDigit())
                                .foregroundStyle(.green)
                            TextField("0.00", value: absPriceBinding(item),
                                      format: .number.precision(.fractionLength(2)))
                                .font(.roundedBody.monospacedDigit())
                                .foregroundStyle(.green)
                                .multilineTextAlignment(.trailing)
                                .keyboardType(.decimalPad)
                                .frame(width: 60)
                        }
                    } else {
                        TextField("0.00", value: priceBinding(item),
                                  format: .number.precision(.fractionLength(2)))
                            .font(.roundedBody.monospacedDigit())
                            .foregroundStyle(Color.textPrimary)
                            .multilineTextAlignment(.trailing)
                            .keyboardType(.decimalPad)
                            .frame(width: 60)
                    }
                } else {
                    Text(isDiscount
                         ? "−$\(abs(item.price), specifier: "%.2f")"
                         : "$\(item.price, specifier: "%.2f")")
                        .font(.roundedBody.monospacedDigit())
                        .foregroundStyle(isDiscount ? Color.green : Color.textPrimary)
                }

                // Category badge (no chevron — tap the row to open picker)
                Text(liveCat.capitalized)
                    .font(.system(size: 10, weight: .semibold, design: .rounded))
                    .foregroundStyle(.white)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 3)
                    .background(categoryColor(for: liveCat))
                    .clipShape(Capsule())

                // Delete button — only visible when row is expanded
                if isExpanded {
                    Button {
                        withAnimation {
                            items.removeAll { $0.id == item.id }
                            editingItemId = nil
                        }
                    } label: {
                        Image(systemName: "trash")
                            .font(.system(size: 13))
                            .foregroundStyle(Color.danger)
                    }
                    .buttonStyle(.plain)
                }
            }
            .padding(.horizontal, 14)
            .padding(.vertical, 9)
            .contentShape(Rectangle())
            .onTapGesture {
                guard isEditMode else { return }
                withAnimation(.spring(duration: 0.2)) {
                    editingItemId = editingItemId == item.id ? nil : item.id
                    if editingItemId != nil { showAddForm = false }
                }
            }

            // Inline category picker — stays open after selection
            if isExpanded {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 6) {
                        ForEach(allCategories, id: \.self) { cat in
                            Button {
                                if let idx = items.firstIndex(where: { $0.id == item.id }) {
                                    items[idx].category = cat
                                }
                            } label: {
                                Text(cat.capitalized)
                                    .font(.system(size: 11, weight: .semibold, design: .rounded))
                                    .foregroundStyle(liveCat == cat ? .white : Color.textSecondary)
                                    .padding(.horizontal, 12)
                                    .padding(.vertical, 5)
                                    .background(liveCat == cat
                                                ? categoryColor(for: cat) : Color.appBackground)
                                    .clipShape(Capsule())
                            }
                            .buttonStyle(.plain)
                        }
                    }
                    .padding(.horizontal, 12)
                    .padding(.bottom, 8)
                }
                .transition(.opacity.combined(with: .move(edge: .top)))
            }
        }
        .background(Color.surface)
        .clipShape(RoundedRectangle(cornerRadius: 10))
        .animation(.spring(duration: 0.2), value: editingItemId)
        .padding(.horizontal)
    }

    // MARK: - Add Item Form

    private var addItemForm: some View {
        VStack(spacing: 10) {
            HStack(spacing: 10) {
                TextField("Item name", text: $newName)
                    .font(.roundedBody)
                    .foregroundStyle(Color.textPrimary)
                    .frame(maxWidth: .infinity)
                TextField("0.00", text: $newPrice)
                    .font(.roundedBody.monospacedDigit())
                    .foregroundStyle(Color.textPrimary)
                    .multilineTextAlignment(.trailing)
                    .keyboardType(.decimalPad)
                    .frame(width: 60)
            }

            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 6) {
                    ForEach(allCategories, id: \.self) { cat in
                        Button { newCategory = cat } label: {
                            Text(cat.capitalized)
                                .font(.system(size: 11, weight: .semibold, design: .rounded))
                                .foregroundStyle(newCategory == cat ? .white : Color.textSecondary)
                                .padding(.horizontal, 12)
                                .padding(.vertical, 6)
                                .background(newCategory == cat
                                            ? categoryColor(for: cat) : Color.appBackground)
                                .clipShape(Capsule())
                        }
                        .buttonStyle(.plain)
                    }
                }
            }

            Button {
                let price = Double(newPrice) ?? 0
                guard !newName.trimmingCharacters(in: .whitespaces).isEmpty else { return }
                let newItem = EditableReceiptItem(name: newName, price: price, category: newCategory)
                withAnimation {
                    items.append(newItem)
                    newName = ""; newPrice = ""; showAddForm = false
                }
                onAdd?(newItem)
            } label: {
                Text("Add Item")
                    .font(.roundedBody).fontWeight(.semibold)
                    .foregroundStyle(.white)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 10)
                    .background(newName.trimmingCharacters(in: .whitespaces).isEmpty
                                ? Color.accent.opacity(0.4) : Color.accent)
                    .clipShape(RoundedRectangle(cornerRadius: 10))
            }
            .disabled(newName.trimmingCharacters(in: .whitespaces).isEmpty)
        }
        .padding(14)
        .background(Color.surface)
        .clipShape(RoundedRectangle(cornerRadius: 14))
        .padding(.horizontal)
        .transition(.opacity.combined(with: .move(edge: .top)))
    }

    // MARK: - Binding Helpers

    private func nameBinding(_ item: EditableReceiptItem) -> Binding<String> {
        Binding(
            get: { items.first(where: { $0.id == item.id })?.name ?? "" },
            set: { if let idx = items.firstIndex(where: { $0.id == item.id }) { items[idx].name = $0 } }
        )
    }

    private func priceBinding(_ item: EditableReceiptItem) -> Binding<Double> {
        Binding(
            get: { items.first(where: { $0.id == item.id })?.price ?? 0 },
            set: { if let idx = items.firstIndex(where: { $0.id == item.id }) { items[idx].price = $0 } }
        )
    }

    private func absPriceBinding(_ item: EditableReceiptItem) -> Binding<Double> {
        Binding(
            get: { abs(items.first(where: { $0.id == item.id })?.price ?? 0) },
            set: { if let idx = items.firstIndex(where: { $0.id == item.id }) { items[idx].price = -abs($0) } }
        )
    }
}
