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

    var body: some View {
        List {
            Section {
                ForEach(categoryManager.categories) { cat in
                    HStack(spacing: 12) {
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
                        }
                    }
                    .listRowBackground(Color.surface)
                    .moveDisabled(cat.name == "other")
                }
                .onMove { source, destination in
                    categoryManager.reorder(from: source, to: destination)
                }
            } header: {
                Text("Drag to reorder categories.")
                    .font(.roundedCaption)
                    .foregroundStyle(Color.textSecondary)
                    .textCase(nil)
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
                    Text("Up to \(categoryManager.maxCustomCategories) custom categories. Names must be unique.")
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
            AddCategorySheet { name, icon in
                categoryManager.addCategory(name: name, icon: icon)
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

// MARK: - Add Category Sheet

@MainActor
struct AddCategorySheet: View {
    @Environment(\.dismiss) private var dismiss
    @State private var name = ""
    @State private var selectedIcon = "tag.fill"
    @State private var showError = false

    let onSave: (String, String) -> Void

    /// Human-readable label for an SF Symbol name.
    private func iconLabel(_ icon: String) -> String {
        icon.replacingOccurrences(of: ".fill", with: "")
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
                // Match on category name or any keyword
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
                        onSave(trimmed, selectedIcon)
                        dismiss()
                    }
                    .font(.roundedHeadline)
                    .foregroundStyle(Color.accent)
                }
            }
        }
    }
}
