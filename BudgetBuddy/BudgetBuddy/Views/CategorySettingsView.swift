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
                    }
                    .listRowBackground(Color.surface)
                    .swipeActions(edge: .trailing, allowsFullSwipe: true) {
                        if !cat.isBuiltin {
                            Button(role: .destructive) {
                                if let idx = categoryManager.categories.firstIndex(of: cat) {
                                    Task {
                                        await categoryManager.deleteCategory(at: idx)
                                        await categoryManager.saveCategories()
                                    }
                                }
                            } label: {
                                Label("Delete", systemImage: "trash")
                            }
                        }
                    }
                }
                .onMove { source, destination in
                    categoryManager.reorder(from: source, to: destination)
                }
            } header: {
                Text("Drag to reorder. Swipe left to delete custom categories.")
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
            .presentationDetents([.medium])
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

    var body: some View {
        NavigationStack {
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

                Spacer()
            }
            .padding()
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
