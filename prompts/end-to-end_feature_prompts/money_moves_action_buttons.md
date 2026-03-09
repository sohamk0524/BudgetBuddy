**Goal**

Add a "Money Moves" row of action-button cards to the Recommendations tab. Each card represents a spending category the user has been active in this month and lets them tap to get category-specific AI recommendations.

---

**Which categories get an action button?**

A category earns a card when **all three** conditions are met:

1. It is one of the 6 recognized sub-categories: `food`, `drink`, `groceries`, `transportation`, `entertainment`, `other`.
2. The user has **at least one positive-amount transaction** in that category during the **current calendar month** (Plaid + manual/voice transactions both count).
3. It ranks in the **top 3** categories by total monthly spend (the iOS client truncates to 3).

Categories with $0 spend this month never appear. The cards are sorted descending by total amount so the highest-spend category is first.

---

**Data model**

Add to `Models.swift`:

```swift
struct MoneyMovesCard: Codable, Identifiable {
    var id: String { category }
    let category: String        // e.g. "food"
    let amount: Double          // total spend this month
    let transactionCount: Int   // number of transactions this month
    let icon: String            // SF Symbol name, e.g. "fork.knife"
}

struct SpendingSummaryResponse: Codable {
    let categories: [MoneyMovesCard]
}
```

---

**Backend — new endpoint**

File: `BudgetBuddyBackend/api/expenses.py`

Add `GET /expenses/spending-summary/<user_id>` (auth required):

1. Query all Plaid + manual transactions for the current month (positive amounts only).
2. Bucket each transaction by `sub_category` into the 6 valid categories.
3. Build a list of categories where `amount > 0`, attaching `category`, `amount`, `transactionCount`, and `icon` (from a `CATEGORY_ICONS` map).
4. Sort descending by `amount` and return `{"categories": [...]}`.

Icon map:

```python
CATEGORY_ICONS = {
    "food": "fork.knife",
    "drink": "cup.and.saucer.fill",
    "groceries": "cart.fill",
    "transportation": "car.fill",
    "entertainment": "theatermasks",
    "other": "ellipsis.circle",
}
```

---

**Backend — category-specific generation**

File: `BudgetBuddyBackend/api/recommendations.py`

The existing `POST /recommendations/generate/<user_id>` endpoint should accept an optional `action` field in the request body (defaults to `"general"`). When `action` is a specific category name (e.g. `"food"`), pass it through to the recommendation generator so the LLM focuses tips on that category.

File: `BudgetBuddyBackend/services/recommendations_generator.py`

When `action` is not `"general"`, prepend a system instruction like: *"Focus all recommendations on the user's {action} spending. Reference their actual transactions and amounts."*

---

**iOS — APIService**

File: `BudgetBuddy/BudgetBuddy/APIService.swift`

Add:
- `getSpendingSummary(userId:) async throws -> SpendingSummaryResponse` — calls the new endpoint.
- `generateRecommendations(userId:action:) async throws -> RecommendationsResponse` — passes `action` in the request body.

---

**iOS — ViewModel**

File: `BudgetBuddy/BudgetBuddy/RecommendationsViewModel.swift`

State:
- `moneyMovesCards: [MoneyMovesCard]` — populated on load.
- `activeCategory: String?` — the currently selected category filter (nil = general).
- `generalRecommendations: [RecommendationItem]` — stashed copy of general recs so the user can return to them.

Actions:
- `loadSpendingSummary()` — fetch spending summary, take the first 3 categories.
- `selectCategory(_ category:)` — stash current recs, set `activeCategory`, call `generateRecommendations(action: category)`.
- `clearCategoryFilter()` — reset `activeCategory` to nil, restore `generalRecommendations`.

Computed:
- `displayedRecommendations` — when a category is active, filter recommendations by keyword matching against `categoryKeywords` (a static dictionary mapping each category to related search terms like `["food", "restaurant", "dining", ...]`).

---

**iOS — View**

File: `BudgetBuddy/BudgetBuddy/Views/RecommendationsView.swift`

1. **Money Moves row**: A horizontal `ScrollView` of `MoneyMovesCardView` cards, shown only when `activeCategory == nil` and `moneyMovesCards` is non-empty. Each card displays the icon, capitalized category name, dollar amount, transaction count, and a "Get tips →" CTA button.

2. **Category chip**: When a category is active, replace the Money Moves row with a dismissible capsule chip showing the category icon + name + an "✕" button. Tapping it calls `clearCategoryFilter()`.

3. **Loading state**: When `activeCategory != nil` and `isGenerating` is true but `displayedRecommendations` is empty, show a centered spinner with "Finding {category} tips…" text.

---

**Constraints**

- SwiftUI only — no UIKit.
- `@Observable` / `@State`, not `ObservableObject`.
- Rounded font design (`.rounded`) for all text.
- Dark mode compatible — use existing color tokens.
- No new dependencies.
