//
//  CategorySettingsView.swift
//  BudgetBuddy
//
//  Settings screen for managing expense categories: reorder, add custom, delete custom.
//

import SwiftUI

@MainActor
struct CategorySettingsView: View {
    @State private var categoryManager = CategoryManager.shared
    @State private var showAddSheet = false

    private func limitBinding(for name: String) -> Binding<Double?> {
        Binding(
            get: { categoryManager.categories.first(where: { $0.name == name })?.weeklyLimit },
            set: { newValue in categoryManager.setWeeklyLimit(for: name, limit: newValue) }
        )
    }

    /// Fixed width for the delete button column so all rows align.
    private let deleteColumnWidth: CGFloat = 28

    var body: some View {
        List {
            Section {
                ForEach(categoryManager.categories) { cat in
                    HStack(spacing: 10) {
                        Image(systemName: cat.icon)
                            .font(.system(size: 16))
                            .foregroundStyle(categoryColor(for: cat.name))
                            .frame(width: 36, height: 36)
                            .background(categoryColor(for: cat.name).opacity(0.15))
                            .clipShape(RoundedRectangle(cornerRadius: 8))

                        Text(cat.displayName)
                            .font(.roundedBody)
                            .foregroundStyle(Color.textPrimary)

                        Spacer()

                        HStack(spacing: 3) {
                            Text("$")
                                .font(.roundedBody)
                                .foregroundStyle(Color.textSecondary)
                            TextField("—", value: limitBinding(for: cat.name), format: .number)
                                .font(.roundedBody)
                                .foregroundStyle(Color.accent)
                                .keyboardType(.decimalPad)
                                .frame(width: 50)
                                .multilineTextAlignment(.trailing)
                            Text("/wk")
                                .font(.roundedCaption)
                                .foregroundStyle(Color.textSecondary)
                        }

                        // Delete button column — fixed width for alignment
                        if !cat.isBuiltin {
                            Button {
                                if let idx = categoryManager.categories.firstIndex(of: cat) {
                                    Task {
                                        await categoryManager.deleteCategory(at: idx)
                                        await categoryManager.saveCategories()
                                    }
                                }
                            } label: {
                                Image(systemName: "trash")
                                    .font(.system(size: 14))
                                    .foregroundStyle(Color.danger)
                            }
                            .buttonStyle(.plain)
                            .frame(width: deleteColumnWidth)
                        } else {
                            Spacer()
                                .frame(width: deleteColumnWidth)
                        }
                    }
                    .listRowBackground(Color.surface)
                    // Note: "Other" reorder is allowed visually but reindex() snaps it back to last
                }
                .onMove { source, destination in
                    categoryManager.reorder(from: source, to: destination)
                }
            } header: {
                Text("Drag to reorder categories.")
                    .font(.roundedCaption)
                    .foregroundStyle(Color.textSecondary)
                    .textCase(nil)
            } footer: {
                if categoryManager.weeklyBudget > 0 {
                    let allocated = categoryManager.totalCategoryLimits
                    let total = categoryManager.weeklyBudget
                    let remaining = categoryManager.remainingBudget
                    let statusColor: Color = {
                        if allocated > total { return .danger }
                        if allocated == total { return .yellow }
                        return .green
                    }()

                    HStack(spacing: 4) {
                        Image(systemName: allocated > total ? "exclamationmark.triangle.fill" : "checkmark.circle.fill")
                            .font(.system(size: 12))
                            .foregroundStyle(statusColor)

                        Text("$\(allocated, specifier: "%.0f") of $\(total, specifier: "%.0f") weekly budget allocated")
                            .font(.roundedCaption)
                            .foregroundStyle(statusColor)

                        if remaining > 0 {
                            Text("($\(remaining, specifier: "%.0f") left)")
                                .font(.roundedCaption)
                                .foregroundStyle(statusColor)
                        }
                    }
                    .padding(.top, 4)
                }
            }

            if categoryManager.canAddMore {
                Section {
                    Button {
                        showAddSheet = true
                    } label: {
                        HStack {
                            Image(systemName: "plus.circle.fill")
                                .foregroundStyle(Color.accent)
                            Text("Add Category")
                                .font(.roundedBody)
                                .foregroundStyle(Color.accent)
                        }
                    }
                    .listRowBackground(Color.surface)
                } footer: {
                    let slotsLeft = categoryManager.maxCustomCategories - categoryManager.customCategories.count
                    Text("\(slotsLeft) of \(categoryManager.maxCustomCategories) custom category slots remaining.")
                        .font(.roundedCaption)
                        .foregroundStyle(Color.textSecondary)
                }
            }
        }
        .listStyle(.insetGrouped)
        .scrollContentBackground(.hidden)
        .background(Color.appBackground)
        .navigationTitle("Categories")
        .navigationBarTitleDisplayMode(.inline)
        .toolbarColorScheme(.dark, for: .navigationBar)
        .environment(\.editMode, .constant(.active))
        .sheet(isPresented: $showAddSheet) {
            AddCategorySheet { name, icon, weeklyLimit in
                categoryManager.addCategory(name: name, icon: icon)
                if let limit = weeklyLimit {
                    categoryManager.setWeeklyLimit(for: name.lowercased(), limit: limit)
                }
                Task { await categoryManager.saveCategories() }
            }
            .presentationDetents([.medium, .large])
            .presentationDragIndicator(.visible)
        }
        .onDisappear {
            Task { await categoryManager.saveCategories() }
        }
    }
}

// MARK: - Icon Display Names

/// Human-readable names for SF Symbols used in the icon picker.
private let iconDisplayNames: [String: String] = [
    "tag.fill": "Tag",
    "briefcase.fill": "Work",
    "house.fill": "Home",
    "cross.case.fill": "Medical",
    "graduationcap.fill": "Education",
    "airplane": "Travel",
    "tshirt.fill": "Clothing",
    "scissors": "Salon",
    "pawprint.fill": "Pets",
    "gift.fill": "Gifts",
    "iphone": "Tech",
    "banknote.fill": "Bills",
    "dumbbell.fill": "Fitness",
    "music.note": "Music",
    "book.fill": "Books",
    "paintbrush.fill": "Art",
    "sparkles": "Beauty",
    "soccerball": "Sports",
    "gamecontroller.fill": "Gaming",
    "bag.fill": "Shopping",
    "lightbulb.fill": "Utilities",
    "wrench.and.screwdriver.fill": "Repairs",
    "leaf.fill": "Nature",
    "heart.fill": "Wellness",
]

// MARK: - Add Category Sheet

@MainActor
struct AddCategorySheet: View {
    @Environment(\.dismiss) private var dismiss
    @State private var name = ""
    @State private var selectedIcon = "tag.fill"
    @State private var weeklyLimit: Double?
    @State private var showError = false

    let onSave: (String, String, Double?) -> Void

    /// Human-readable label for an SF Symbol name.
    private func iconLabel(_ icon: String) -> String {
        iconDisplayNames[icon] ?? icon
            .replacingOccurrences(of: ".fill", with: "")
            .replacingOccurrences(of: ".", with: " ")
            .capitalized
    }

    /// Fuzzy-matched suggestions based on what the user is typing.
    private var filteredSuggestions: [(name: String, info: KnownCategoryInfo)] {
        let query = name.lowercased().trimmingCharacters(in: .whitespacesAndNewlines)
        guard !query.isEmpty else { return [] }
        let activeNames = Set(CategoryManager.shared.categories.map { $0.name })
        return knownCategoryRegistry
            .filter { entry in
                guard !activeNames.contains(entry.key) else { return false }
                if entry.value.displayName.lowercased().contains(query) { return true }
                if entry.key.contains(query) { return true }
                return entry.value.keywords.contains { $0.contains(query) }
            }
            .sorted { $0.value.displayName < $1.value.displayName }
            .map { (name: $0.key, info: $0.value) }
    }

    private func selectSuggestion(_ key: String, _ info: KnownCategoryInfo) {
        name = info.displayName
        selectedIcon = info.icon
    }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 20) {
                    // Name field
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Category Name")
                            .font(.roundedCaption)
                            .foregroundStyle(Color.textSecondary)

                        TextField("e.g. Subscriptions", text: $name)
                            .font(.roundedBody)
                            .foregroundStyle(Color.textPrimary)
                            .padding(12)
                            .background(Color.surface)
                            .clipShape(RoundedRectangle(cornerRadius: 12))
                    }

                    // Weekly limit (optional) — right below the name
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Weekly Limit (optional)")
                            .font(.roundedCaption)
                            .foregroundStyle(Color.textSecondary)

                        HStack(spacing: 6) {
                            Text("$")
                                .font(.roundedBody)
                                .foregroundStyle(Color.textSecondary)
                            TextField("No limit", value: $weeklyLimit, format: .number)
                                .font(.roundedBody)
                                .foregroundStyle(Color.accent)
                                .keyboardType(.decimalPad)
                                .padding(12)
                                .background(Color.surface)
                                .clipShape(RoundedRectangle(cornerRadius: 12))
                            Text("/week")
                                .font(.roundedCaption)
                                .foregroundStyle(Color.textSecondary)
                        }
                    }

                    // Fuzzy suggestions (appear as user types)
                    if !filteredSuggestions.isEmpty {
                        VStack(alignment: .leading, spacing: 6) {
                            ForEach(filteredSuggestions, id: \.name) { item in
                                Button {
                                    selectSuggestion(item.name, item.info)
                                } label: {
                                    HStack(spacing: 10) {
                                        Image(systemName: item.info.icon)
                                            .font(.system(size: 14))
                                            .foregroundStyle(Color.accent)
                                            .frame(width: 24)
                                        Text(item.info.displayName)
                                            .font(.roundedBody)
                                            .foregroundStyle(Color.textPrimary)
                                        Spacer()
                                        Image(systemName: "arrow.up.left")
                                            .font(.system(size: 12))
                                            .foregroundStyle(Color.textSecondary)
                                    }
                                    .padding(.horizontal, 12)
                                    .padding(.vertical, 10)
                                    .background(Color.surface)
                                    .clipShape(RoundedRectangle(cornerRadius: 10))
                                }
                                .buttonStyle(.plain)
                            }
                        }
                    }

                    // Icon picker
                    VStack(alignment: .leading, spacing: 8) {
                        HStack(spacing: 6) {
                            Text("Choose an Icon")
                                .font(.roundedCaption)
                                .foregroundStyle(Color.textSecondary)
                            Text("— \(iconLabel(selectedIcon))")
                                .font(.roundedCaption)
                                .foregroundStyle(Color.accent)
                        }

                        LazyVGrid(columns: Array(repeating: GridItem(.flexible()), count: 6), spacing: 10) {
                            ForEach(CategoryManager.iconOptions, id: \.self) { icon in
                                Button {
                                    selectedIcon = icon
                                } label: {
                                    Image(systemName: icon)
                                        .font(.system(size: 18))
                                        .foregroundStyle(selectedIcon == icon ? Color.accent : Color.textSecondary)
                                        .frame(width: 44, height: 44)
                                        .background(selectedIcon == icon ? Color.accent.opacity(0.2) : Color.surface)
                                        .clipShape(RoundedRectangle(cornerRadius: 10))
                                        .overlay(
                                            RoundedRectangle(cornerRadius: 10)
                                                .stroke(selectedIcon == icon ? Color.accent : Color.clear, lineWidth: 2)
                                        )
                                }
                                .buttonStyle(.plain)
                            }
                        }
                    }

                    if showError {
                        Text("Name must be unique and non-empty.")
                            .font(.roundedCaption)
                            .foregroundStyle(Color.danger)
                    }
                }
                .padding()
            }
            .background(Color.appBackground)
            .navigationTitle("New Category")
            .navigationBarTitleDisplayMode(.inline)
            .toolbarColorScheme(.dark, for: .navigationBar)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                        .foregroundStyle(Color.textSecondary)
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Add") {
                        let trimmed = name.trimmingCharacters(in: .whitespacesAndNewlines)
                        guard !trimmed.isEmpty,
                              !CategoryManager.shared.categories.contains(where: {
                                  $0.name == trimmed.lowercased()
                              }) else {
                            showError = true
                            return
                        }
                        onSave(trimmed, selectedIcon, weeklyLimit)
                        dismiss()
                    }
                    .font(.roundedHeadline)
                    .foregroundStyle(Color.accent)
                }
            }
        }
    }
}
