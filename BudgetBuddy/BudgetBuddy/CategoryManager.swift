//
//  CategoryManager.swift
//  BudgetBuddy
//
//  Centralized manager for expense categories (built-in + user custom).
//  All category pickers, filters, and helpers delegate to this singleton.
//

import SwiftUI

// MARK: - UserCategory Model

struct UserCategory: Identifiable, Codable, Equatable, Hashable {
    var id: UUID
    var name: String        // lowercase key: "food", "coffee"
    var displayName: String // title case: "Food", "Coffee"
    var icon: String        // SF Symbol name: "fork.knife", "tag.fill"
    var isBuiltin: Bool
    var displayOrder: Int

    static let builtins: [UserCategory] = [
        .init(id: UUID(), name: "food", displayName: "Food", icon: "fork.knife", isBuiltin: true, displayOrder: 0),
        .init(id: UUID(), name: "drink", displayName: "Drink", icon: "cup.and.saucer.fill", isBuiltin: true, displayOrder: 1),
        .init(id: UUID(), name: "groceries", displayName: "Groceries", icon: "cart.fill", isBuiltin: true, displayOrder: 2),
        .init(id: UUID(), name: "transportation", displayName: "Transportation", icon: "car.fill", isBuiltin: true, displayOrder: 3),
        .init(id: UUID(), name: "entertainment", displayName: "Entertainment", icon: "film.fill", isBuiltin: true, displayOrder: 4),
        .init(id: UUID(), name: "other", displayName: "Other", icon: "ellipsis.circle.fill", isBuiltin: true, displayOrder: 5),
    ]
}

// MARK: - CategoryManager

@Observable
@MainActor
class CategoryManager {

    static let shared = CategoryManager()

    private(set) var categories: [UserCategory] = UserCategory.builtins

    private let defaults = UserDefaults.standard
    private let cacheKey = "user_categories"

    var maxCustomCategories: Int { 4 }

    var customCategories: [UserCategory] {
        categories.filter { !$0.isBuiltin }
    }

    var canAddMore: Bool {
        customCategories.count < maxCustomCategories
    }

    /// SF Symbol options for custom categories.
    static let iconOptions = [
        "tag.fill", "briefcase.fill", "house.fill", "cross.case.fill",
        "graduationcap.fill", "airplane", "tshirt.fill", "scissors",
        "pawprint.fill", "gift.fill", "iphone", "banknote.fill",
        "dumbbell.fill", "music.note", "book.fill", "paintbrush.fill",
        "sparkles", "soccerball", "gamecontroller.fill", "bag.fill",
        "lightbulb.fill", "wrench.and.screwdriver.fill", "leaf.fill", "heart.fill",
    ]

    // MARK: - Init

    private init() {
        loadFromCache()
    }

    // MARK: - Cache

    private func loadFromCache() {
        guard let data = defaults.data(forKey: cacheKey),
              let cached = try? JSONDecoder().decode([UserCategory].self, from: data) else { return }
        if !cached.isEmpty { categories = cached }
    }

    private func saveToCache() {
        if let data = try? JSONEncoder().encode(categories) {
            defaults.set(data, forKey: cacheKey)
        }
    }

    // MARK: - API Sync

    func loadCategories() async {
        guard let userId = AuthManager.shared.authToken else { return }
        do {
            let prefs = try await APIService.shared.getCategoryPreferences(userId: userId)
            if !prefs.isEmpty {
                categories = prefs.enumerated().map { idx, pref in
                    let name = pref.categoryName.lowercased()
                    let builtinNames = Set(UserCategory.builtins.map { $0.name })
                    let isBuiltin = pref.isBuiltin ?? builtinNames.contains(name)
                    return UserCategory(
                        id: UUID(),
                        name: name,
                        displayName: pref.categoryName.capitalized,
                        icon: pref.emoji ?? defaultIcon(for: name),
                        isBuiltin: isBuiltin,
                        displayOrder: pref.displayOrder ?? idx
                    )
                }
                saveToCache()
            }
        } catch {
            print("Failed to load category preferences: \(error)")
        }
    }

    func saveCategories() async {
        guard let userId = AuthManager.shared.authToken else { return }
        let payload = categories.map { cat -> [String: Any] in
            ["name": cat.name, "emoji": cat.icon, "isBuiltin": cat.isBuiltin]
        }
        do {
            try await APIService.shared.updateCategoryPreferences(userId: userId, categories: payload)
            saveToCache()
        } catch {
            print("Failed to save category preferences: \(error)")
        }
    }

    // MARK: - Mutations

    func addCategory(name: String, icon: String) {
        guard canAddMore else { return }
        let lowerName = name.lowercased().trimmingCharacters(in: .whitespacesAndNewlines)
        guard !lowerName.isEmpty,
              !categories.contains(where: { $0.name == lowerName }) else { return }

        let newCat = UserCategory(
            id: UUID(),
            name: lowerName,
            displayName: name.trimmingCharacters(in: .whitespacesAndNewlines),
            icon: icon,
            isBuiltin: false,
            displayOrder: categories.count
        )
        // Insert right above "Other" so it's always last
        if let otherIdx = categories.firstIndex(where: { $0.name == "other" }) {
            categories.insert(newCat, at: otherIdx)
        } else {
            categories.append(newCat)
        }
        reindex()
        saveToCache()
    }

    func deleteCategory(at index: Int) async {
        guard index < categories.count, !categories[index].isBuiltin else { return }
        let cat = categories[index]
        categories.remove(at: index)
        reindex()
        saveToCache()

        // Backend: migrate transactions to "other" and delete the preference
        guard let userId = AuthManager.shared.authToken else { return }
        do {
            try await APIService.shared.deleteCustomCategory(
                userId: userId, categoryName: cat.name, migrateTo: "other"
            )
        } catch {
            print("Failed to delete category on backend: \(error)")
        }
    }

    func reorder(from source: IndexSet, to destination: Int) {
        categories.move(fromOffsets: source, toOffset: destination)
        reindex()
        saveToCache()
    }

    private func reindex() {
        for i in categories.indices {
            categories[i].displayOrder = i
        }
    }

    func clearData() {
        categories = UserCategory.builtins
        defaults.removeObject(forKey: cacheKey)
    }

    // MARK: - Helpers

    func isValidCategory(_ name: String) -> Bool {
        categories.contains { $0.name == name.lowercased() }
    }

    func displayName(for category: String) -> String {
        categories.first { $0.name == category.lowercased() }?.displayName ?? category.capitalized
    }

    func icon(for category: String) -> String {
        categories.first { $0.name == category.lowercased() }?.icon ?? defaultIcon(for: category)
    }

    func color(for category: String) -> Color {
        switch category.lowercased() {
        case "food": return .orange
        case "drink": return .brown
        case "groceries": return .green
        case "transportation": return .blue
        case "entertainment": return .purple
        case "other": return .gray
        default:
            // Custom category colors from a palette
            let customIdx = customCategories.firstIndex { $0.name == category.lowercased() } ?? 0
            let palette: [Color] = [.pink, .cyan, .mint, .indigo]
            return palette[customIdx % palette.count]
        }
    }

    private func defaultIcon(for category: String) -> String {
        switch category.lowercased() {
        case "food": return "fork.knife"
        case "drink": return "cup.and.saucer.fill"
        case "groceries": return "cart.fill"
        case "transportation": return "car.fill"
        case "entertainment": return "film.fill"
        case "other": return "ellipsis.circle.fill"
        default: return "tag.fill"
        }
    }
}
