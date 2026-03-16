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
    var weeklyLimit: Double? // optional per-category weekly spending limit

    static let builtins: [UserCategory] = [
        .init(id: UUID(), name: "food", displayName: "Food", icon: "fork.knife", isBuiltin: true, displayOrder: 0),
        .init(id: UUID(), name: "drink", displayName: "Drink", icon: "cup.and.saucer.fill", isBuiltin: true, displayOrder: 1),
        .init(id: UUID(), name: "groceries", displayName: "Groceries", icon: "cart.fill", isBuiltin: true, displayOrder: 2),
        .init(id: UUID(), name: "transportation", displayName: "Transportation", icon: "car.fill", isBuiltin: true, displayOrder: 3),
        .init(id: UUID(), name: "entertainment", displayName: "Entertainment", icon: "film.fill", isBuiltin: true, displayOrder: 4),
        .init(id: UUID(), name: "other", displayName: "Other", icon: "ellipsis.circle.fill", isBuiltin: true, displayOrder: 5),
    ]
}

// MARK: - Known Category Registry
/// Pre-defined metadata for categories we know how to classify. When a user adds
/// one of these as a custom category, we auto-fill the icon, color, and supply
/// keywords to the LLM and recommendation engine. Unknown custom names still work
/// with basic fallbacks.

struct KnownCategoryInfo {
    let displayName: String
    let icon: String           // SF Symbol
    let color: String          // Color name (resolved at runtime)
    let keywords: [String]     // For LLM classification & recommendation filtering
}

/// Master registry — builtins + all anticipated custom categories.
/// Add new entries here to teach the system about a category before any user creates it.
let knownCategoryRegistry: [String: KnownCategoryInfo] = [
    // Builtins
    "food":            .init(displayName: "Food",            icon: "fork.knife",              color: "orange",  keywords: ["food", "restaurant", "dining", "eat", "meal", "lunch", "dinner", "breakfast", "fast food", "chipotle", "mcdonald", "burger", "pizza", "sushi", "taco"]),
    "drink":           .init(displayName: "Drink",           icon: "cup.and.saucer.fill",     color: "brown",   keywords: ["drink", "coffee", "cafe", "tea", "starbucks", "boba", "bar", "smoothie", "juice", "beer", "wine", "cocktail"]),
    "groceries":       .init(displayName: "Groceries",       icon: "cart.fill",               color: "green",   keywords: ["grocery", "groceries", "supermarket", "trader joe", "walmart", "costco", "aldi", "whole foods", "safeway", "kroger", "target"]),
    "transportation":  .init(displayName: "Transportation",  icon: "car.fill",                color: "blue",    keywords: ["transport", "gas", "uber", "lyft", "ride", "bus", "transit", "parking", "fuel", "metro", "taxi", "toll", "car wash"]),
    "entertainment":   .init(displayName: "Entertainment",   icon: "film.fill",               color: "purple",  keywords: ["entertainment", "movie", "streaming", "spotify", "netflix", "gaming", "concert", "event", "theater", "hulu", "disney", "youtube"]),
    "other":           .init(displayName: "Other",           icon: "ellipsis.circle.fill",    color: "gray",    keywords: ["subscription", "recurring", "amazon", "online", "miscellaneous"]),

    // Known custom categories — pre-planned with rich metadata
    "cosmetics":       .init(displayName: "Cosmetics",       icon: "paintbrush.fill",         color: "pink",    keywords: ["cosmetics", "makeup", "beauty", "skincare", "sephora", "ulta", "mascara", "lipstick", "foundation", "concealer", "lotion", "serum", "facial"]),
    "subscriptions":   .init(displayName: "Subscriptions",   icon: "arrow.triangle.2.circlepath", color: "indigo", keywords: ["subscription", "recurring", "monthly", "annual", "netflix", "spotify", "hulu", "apple", "icloud", "membership", "patreon", "substack"]),
    "health":          .init(displayName: "Health",          icon: "cross.case.fill",         color: "red",     keywords: ["health", "medical", "doctor", "pharmacy", "hospital", "dental", "vision", "therapy", "prescription", "cvs", "walgreens", "insurance", "copay"]),
    "fitness":         .init(displayName: "Fitness",         icon: "dumbbell.fill",           color: "mint",    keywords: ["fitness", "gym", "workout", "yoga", "pilates", "peloton", "crossfit", "training", "sport", "running", "exercise"]),
    "shopping":        .init(displayName: "Shopping",        icon: "bag.fill",                color: "teal",    keywords: ["shopping", "clothes", "clothing", "shoes", "apparel", "fashion", "mall", "retail", "zara", "h&m", "nike", "adidas", "nordstrom"]),
    "education":       .init(displayName: "Education",       icon: "graduationcap.fill",      color: "cyan",    keywords: ["education", "tuition", "school", "university", "course", "textbook", "udemy", "coursera", "student", "learning", "class"]),
    "travel":          .init(displayName: "Travel",          icon: "airplane",                color: "blue",    keywords: ["travel", "flight", "hotel", "airbnb", "booking", "vacation", "trip", "airline", "luggage", "hostel", "resort"]),
    "pets":            .init(displayName: "Pets",            icon: "pawprint.fill",           color: "brown",   keywords: ["pet", "pets", "vet", "veterinary", "dog", "cat", "petco", "petsmart", "grooming", "kibble", "treats"]),
    "home":            .init(displayName: "Home",            icon: "house.fill",              color: "orange",  keywords: ["home", "rent", "mortgage", "utilities", "electric", "water", "internet", "furniture", "ikea", "maintenance", "repair", "cleaning"]),
    "gifts":           .init(displayName: "Gifts",           icon: "gift.fill",               color: "red",     keywords: ["gift", "gifts", "present", "birthday", "holiday", "christmas", "donation", "charity", "wedding"]),
    "tech":            .init(displayName: "Tech",            icon: "iphone",                  color: "gray",    keywords: ["tech", "technology", "electronics", "computer", "phone", "apple store", "best buy", "software", "gadget", "accessory", "charger"]),
    "music":           .init(displayName: "Music",           icon: "music.note",              color: "pink",    keywords: ["music", "concert", "vinyl", "instrument", "guitar", "piano", "spotify", "apple music", "tickets", "festival"]),
    "books":           .init(displayName: "Books",           icon: "book.fill",               color: "brown",   keywords: ["book", "books", "kindle", "audible", "bookstore", "library", "reading", "novel", "audiobook", "barnes"]),
    "gaming":          .init(displayName: "Gaming",          icon: "gamecontroller.fill",     color: "indigo",  keywords: ["gaming", "game", "playstation", "xbox", "nintendo", "steam", "twitch", "esports", "console", "pc gaming"]),
    "utilities":       .init(displayName: "Utilities",       icon: "lightbulb.fill",          color: "yellow",  keywords: ["utility", "utilities", "electric", "water", "gas bill", "internet", "phone bill", "sewage", "trash", "power"]),
    "insurance":       .init(displayName: "Insurance",       icon: "shield.fill",             color: "blue",    keywords: ["insurance", "premium", "coverage", "deductible", "auto insurance", "health insurance", "renters", "life insurance", "geico", "state farm"]),
    "savings":         .init(displayName: "Savings",         icon: "banknote.fill",           color: "green",   keywords: ["savings", "investment", "invest", "stock", "401k", "ira", "deposit", "transfer", "robinhood", "vanguard", "fidelity"]),
    "personal care":   .init(displayName: "Personal Care",   icon: "sparkles",                color: "pink",    keywords: ["personal care", "haircut", "salon", "barber", "spa", "nails", "manicure", "pedicure", "waxing", "massage"]),
    "clothing":        .init(displayName: "Clothing",        icon: "tshirt.fill",             color: "indigo",  keywords: ["clothing", "clothes", "shoes", "apparel", "fashion", "outfit", "dress", "jacket", "pants", "shirt"]),
    "repairs":         .init(displayName: "Repairs",         icon: "wrench.and.screwdriver.fill", color: "gray", keywords: ["repair", "fix", "maintenance", "mechanic", "plumber", "electrician", "handyman", "service", "auto repair"]),
]

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
        if !cached.isEmpty {
            categories = cached
            reindex()  // ensures "other" is last
        }
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
                        displayOrder: pref.displayOrder ?? idx,
                        weeklyLimit: pref.weeklyLimit
                    )
                }
                reindex()  // ensures "other" is last
                saveToCache()
            }
        } catch {
            print("Failed to load category preferences: \(error)")
        }
    }

    func saveCategories() async {
        guard let userId = AuthManager.shared.authToken else { return }
        let payload = categories.map { cat -> [String: Any] in
            var dict: [String: Any] = ["name": cat.name, "emoji": cat.icon, "isBuiltin": cat.isBuiltin]
            if let limit = cat.weeklyLimit {
                dict["weeklyLimit"] = limit
            }
            return dict
        }
        do {
            try await APIService.shared.updateCategoryPreferences(userId: userId, categories: payload)
            saveToCache()
        } catch {
            print("Failed to save category preferences: \(error)")
        }
    }

    // MARK: - Mutations

    /// Sum of all per-category weekly limits currently set.
    var totalCategoryLimits: Double {
        categories.compactMap(\.weeklyLimit).reduce(0, +)
    }

    /// The user's overall weekly spending goal from profile.
    var weeklyBudget: Double {
        UserDefaults.standard.double(forKey: "profile_weeklyLimit")
    }

    /// How much of the weekly budget is still unallocated to categories.
    var remainingBudget: Double {
        max(0, weeklyBudget - totalCategoryLimits)
    }

    func setWeeklyLimit(for categoryName: String, limit: Double?) {
        guard let idx = categories.firstIndex(where: { $0.name == categoryName }) else { return }
        categories[idx].weeklyLimit = limit
        saveToCache()
    }

    func addCategory(name: String, icon: String? = nil) {
        guard canAddMore else { return }
        let lowerName = name.lowercased().trimmingCharacters(in: .whitespacesAndNewlines)
        guard !lowerName.isEmpty,
              !categories.contains(where: { $0.name == lowerName }) else { return }

        // Auto-fill icon from registry if not explicitly provided
        let resolvedIcon = icon ?? knownCategoryRegistry[lowerName]?.icon ?? "tag.fill"
        let resolvedDisplayName = knownCategoryRegistry[lowerName]?.displayName
            ?? name.trimmingCharacters(in: .whitespacesAndNewlines)

        let newCat = UserCategory(
            id: UUID(),
            name: lowerName,
            displayName: resolvedDisplayName,
            icon: resolvedIcon,
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
        // Ensure "other" is always last
        if let otherIdx = categories.firstIndex(where: { $0.name == "other" }),
           otherIdx != categories.count - 1 {
            let other = categories.remove(at: otherIdx)
            categories.append(other)
        }
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

    private static let colorMap: [String: Color] = [
        "orange": .orange, "brown": .brown, "green": .green, "blue": .blue,
        "purple": .purple, "gray": .gray, "pink": .pink, "indigo": .indigo,
        "red": .red, "mint": .mint, "cyan": .cyan, "teal": .teal, "yellow": .yellow,
    ]

    func color(for category: String) -> Color {
        let key = category.lowercased()
        if let info = knownCategoryRegistry[key],
           let color = Self.colorMap[info.color] {
            return color
        }
        // Unknown custom category — assign from palette by index
        let customIdx = customCategories.firstIndex { $0.name == key } ?? 0
        let palette: [Color] = [.pink, .cyan, .mint, .indigo]
        return palette[customIdx % palette.count]
    }

    func defaultIcon(for category: String) -> String {
        knownCategoryRegistry[category.lowercased()]?.icon ?? "tag.fill"
    }

    /// Keywords for a category — used by recommendation filtering and LLM prompts.
    func keywords(for category: String) -> [String] {
        let key = category.lowercased()
        if let info = knownCategoryRegistry[key] {
            return info.keywords
        }
        // Unknown custom category — just use the name itself
        return [key]
    }

    /// Returns all known category names that aren't currently active (for suggestions).
    var suggestedCategories: [KnownCategoryInfo] {
        let activeNames = Set(categories.map { $0.name })
        return knownCategoryRegistry
            .filter { !activeNames.contains($0.key) }
            .sorted { $0.key < $1.key }
            .map { $0.value }
    }
}
