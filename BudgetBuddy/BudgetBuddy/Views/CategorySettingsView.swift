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
    @State private var isSaving = false

    var body: some View {
        List {
            Section {
                ForEach(categoryManager.categories) { cat in
                    HStack(spacing: 12) {
                        Text(cat.emoji)
                            .font(.title2)
                            .frame(width: 36)

                        VStack(alignment: .leading, spacing: 2) {
                            Text(cat.displayName)
                                .font(.roundedBody)
                                .foregroundStyle(Color.textPrimary)
                            if cat.isBuiltin {
                                Text("Built-in")
                                    .font(.roundedCaption)
                                    .foregroundStyle(Color.textSecondary)
                            } else {
                                Text("Custom")
                                    .font(.roundedCaption)
                                    .foregroundStyle(Color.accent)
                            }
                        }

                        Spacer()

                        Image(systemName: "line.3.horizontal")
                            .foregroundStyle(Color.textSecondary)
                            .font(.system(size: 14))
                    }
                    .listRowBackground(Color.surface)
                    .swipeActions(edge: .trailing) {
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
                Text("Drag to reorder. Swipe custom categories to delete.")
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
            AddCategorySheet { name, emoji in
                categoryManager.addCategory(name: name, emoji: emoji)
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
    @State private var selectedEmoji = "🏷️"
    @State private var showError = false

    let onSave: (String, String) -> Void

    private let emojiOptions = [
        "🏷️", "💼", "🏠", "💊", "🎓", "✈️", "👕", "💇",
        "🐶", "🎁", "📱", "💰", "🏋️", "🎵", "📚", "🍕",
        "🧹", "⚽", "🎮", "🛍️", "💡", "🔧", "🌿", "❤️",
    ]

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

                // Emoji picker
                VStack(alignment: .leading, spacing: 8) {
                    Text("Choose an Emoji")
                        .font(.roundedCaption)
                        .foregroundStyle(Color.textSecondary)

                    LazyVGrid(columns: Array(repeating: GridItem(.flexible()), count: 8), spacing: 10) {
                        ForEach(emojiOptions, id: \.self) { emoji in
                            Button {
                                selectedEmoji = emoji
                            } label: {
                                Text(emoji)
                                    .font(.title2)
                                    .frame(width: 40, height: 40)
                                    .background(selectedEmoji == emoji ? Color.accent.opacity(0.2) : Color.clear)
                                    .clipShape(RoundedRectangle(cornerRadius: 8))
                                    .overlay(
                                        RoundedRectangle(cornerRadius: 8)
                                            .stroke(selectedEmoji == emoji ? Color.accent : Color.clear, lineWidth: 2)
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
                        onSave(trimmed, selectedEmoji)
                        dismiss()
                    }
                    .font(.roundedHeadline)
                    .foregroundStyle(Color.accent)
                }
            }
        }
    }
}
