# BudgetBuddy: Weekly Budgets — Global Spending Limit on Bar Chart & Per-Category Budget Limits

## Context

This feature extends the existing Insights tab with two budget-tracking capabilities:

1. **Global weekly spending limit visualization** on the existing "Spending Over Time" bar chart — a dashed budget line, color-coded bars (red when over budget), and a status callout showing how many days/weeks exceeded the limit.
2. **Per-category weekly budget limits** — users can optionally set a weekly spending limit on any category in Settings → Categories, and a new "Category Budgets" bar chart card on the Insights tab visualizes spending vs. limits for all categories that have one set.

Both features share the same weekly spending goal stored in the user's profile (`profile_weeklyLimit` in UserDefaults). Per-category limits are stored alongside each category's preferences in Google Cloud Datastore and synced via the existing category preferences API.

All changes are backward-compatible — `weeklyLimit` is optional/nil by default, so existing users and categories are unaffected.

---

## Feature 1: Global Spending Limit on "Spending Over Time" Bar Chart

The existing bar chart already shows daily or weekly spending bars. This feature overlays a budget reference line and colors bars red when they exceed the limit.

### Feature 1 — Backend

No backend changes required. The weekly spending limit is already stored in the user profile and read from `UserDefaults` on iOS via `profile_weeklyLimit`.

### Feature 1 — iOS: InsightsViewModel

**`BudgetBuddy/BudgetBuddy/InsightsViewModel.swift`**

Add the following computed properties and methods after the existing state properties:

- **`weeklyBudget: Double`** — reads from `UserDefaults.standard.double(forKey: "profile_weeklyLimit")`
- **`barBudgetLimit: Double?`** — returns `nil` if no budget set; returns `weeklyBudget / 7.0` for daily grouping or `weeklyBudget` for weekly grouping
- **`isOverBudget(_ entry: BarEntry) -> Bool`** — returns `true` if the entry's amount exceeds `barBudgetLimit`
- **`overBudgetCount: Int`** — count of bars with spending that exceed the limit
- **`barsWithSpending: Int`** — count of bars with amount > 0

### Feature 1 — iOS: InsightsView

**`BudgetBuddy/BudgetBuddy/Views/InsightsView.swift`**

Modify the existing `barChartCard` section:

**Average & Target row** (below the Daily/Weekly toggle):
- Left side: "{unit} Average: $X" in secondary text
- Right side (only if budget is set): "{unit} Target: $Y" colored with `budgetStatusColor`
- `budgetStatusColor` computed property: green if 0 bars over budget, yellow if some over, red if all over

**Budget status callout** (below the average row):
- If budget is set: Show icon + "X of Y {days/weeks} over budget" or "All within budget" text, colored with `budgetStatusColor`
  - `checkmark.circle.fill` icon when none over, `exclamationmark.triangle.fill` when some/all over
- If no budget: Show a `NavigationLink` to ProfileView with prompt "Set a weekly budget to track spending limits"

**Chart modifications:**
- Add `RuleMark(y: .value("Budget", limit))` with dashed red line style (`StrokeStyle(lineWidth: 1.5, dash: [6, 4])`)
- Add Y-axis `AxisMarks(position: .leading, values: [limit])` showing "Budget" label in red
- Color bars using `barColor(for:)` helper: red (`.danger`) when over budget, teal (`.accent`) when under
  - Selected bars are full opacity, unselected bars at 0.5/0.6 opacity
  - Bars are ALWAYS red when over budget (no yellow bars — yellow is only for status text)

**`.walletCard()` modifier** (shared):
- Must use `.background(RoundedRectangle(cornerRadius: 16).fill(Color.surface))` instead of `.clipShape()` to prevent clipping chart axis labels and the last x-axis date label

---

## Feature 2: Per-Category Weekly Budget Limits — Data Model

### Feature 2 — Backend: Datastore

**`BudgetBuddyBackend/db_models.py`**

In `set_category_prefs()`, add `weekly_limit` to entity fields:
```python
'weekly_limit': cat.get('weeklyLimit'),  # None if not set
```

**`BudgetBuddyBackend/api/user.py`**

In the `GET /user/category-preferences/<user_id>` response, add:
```python
"weeklyLimit": p.get('weekly_limit'),
```
The `PUT` endpoint already accepts arbitrary fields in the category dict — no changes needed there since `weeklyLimit` flows through as part of the payload.

### Feature 2 — iOS: Models

**`BudgetBuddy/BudgetBuddy/Models.swift`**

Add `weeklyLimit: Double?` to the `CategoryPreference` struct.

### Feature 2 — iOS: CategoryManager

**`BudgetBuddy/BudgetBuddy/CategoryManager.swift`**

- Add `weeklyLimit: Double?` field to `UserCategory` struct (optional, nil by default)
- In `loadCategories()`: read `weeklyLimit: pref.weeklyLimit` from API response
- In `saveCategories()`: include `weeklyLimit` in the payload dict (only when non-nil)
- Add budget-tracking computed properties:
  - `totalCategoryLimits: Double` — sum of all per-category weekly limits
  - `weeklyBudget: Double` — reads from `UserDefaults` (`profile_weeklyLimit`)
  - `remainingBudget: Double` — `max(0, weeklyBudget - totalCategoryLimits)`
- Add `setWeeklyLimit(for categoryName: String, limit: Double?)` method for indirect mutation (needed because `categories` has `private(set)` access)
- `Codable` auto-synthesis handles the new optional field for cache serialization

---

## Feature 3: Category Settings UI — Weekly Limit Input

### Feature 3 — iOS: CategorySettingsView

**`BudgetBuddy/BudgetBuddy/Views/CategorySettingsView.swift`**

**Each category row** — add inline weekly limit input:
- Layout: `[icon] [name] ... [$ amount /wk] [trash?]`
- Use `limitBinding(for:)` helper that creates a `Binding<Double?>` targeting the category by name via `categoryManager.setWeeklyLimit(for:limit:)`
- `TextField("—", value: limitBinding, format: .number)` with `.keyboardType(.decimalPad)`, width 50, trailing alignment
- Fixed-width column (28pt) for the delete button — builtin categories get an empty `Spacer` of the same width for alignment

**Budget allocation footer** (below the category list section):
- Only shown when `categoryManager.weeklyBudget > 0`
- Text: "$X of $Y weekly budget allocated ($Z left)"
- Color: green if under budget, yellow if exactly at budget, red if over-allocated
- Icon: `checkmark.circle.fill` (under/at) or `exclamationmark.triangle.fill` (over)

**"Add Category" section footer:**
- Text: "X of 4 custom category slots remaining"

**AddCategorySheet updates:**
- Callback signature: `(String, String, Double?) -> Void` (name, icon, optional weeklyLimit)
- Add weekly limit field below the category name input, above suggestions/icon picker:
  - Label: "Weekly Limit (optional)"
  - Layout: `[$ textfield /week]`
  - `.keyboardType(.decimalPad)`, placeholder "No limit"
- On save, call `categoryManager.setWeeklyLimit(for:limit:)` for the new category
- **Icon display names**: Add `iconDisplayNames` dictionary mapping all 24 SF Symbol names to human-readable labels (e.g., `"tag.fill": "Tag"`, `"briefcase.fill": "Work"`, etc.) — shown next to "Choose an Icon" header

---

## Feature 4: Category Budgets Bar Chart on Insights Tab

### Feature 4 — iOS: InsightsViewModel

**`BudgetBuddy/BudgetBuddy/InsightsViewModel.swift`**

Add new data types and computed properties:

```swift
struct CategoryBudgetEntry: Identifiable {
    let id: String
    let category: String
    let displayName: String
    let spent: Double
    let limit: Double
    let color: Color
    let icon: String
    var isOverBudget: Bool { spent > limit }
}
```

- **`categoryBudgetData: [CategoryBudgetEntry]`** — filters `CategoryManager.shared.categories` to those with a `weeklyLimit` set, sums spending from `allTransactions` for the **last 7 days** only (regardless of the date range picker, since limits are weekly), returns entries with spent/limit/color/icon
- **`categoryBudgetOverCount: Int`** — count of categories where `spent > limit`

### Feature 4 — iOS: InsightsView

**`BudgetBuddy/BudgetBuddy/Views/InsightsView.swift`**

Add a new `categoryBudgetsCard` after the existing `barChartCard`:

**Card header:**
- Title: "Category Budgets" (left)
- Subtitle: "Weekly" (right, secondary text)

**Empty state** (no categories have limits set):
- `NavigationLink` to `CategorySettingsView` with prompt: "Set weekly limits per category in Categories settings"

**When data exists:**

**Budget status row:**
- Left: icon + "X of Y categories over budget" / "All within budget" / "All over budget" with green/yellow/red coloring
- Right: `NavigationLink` to `CategorySettingsView` with "Edit Limits" text in accent color

**Bar chart:**
- X-axis: category display names (categorical)
- Y-axis: dollar amounts with leading axis marks
- **Spending bars**: green (`.green`) when under limit, red (`.danger`) when over
- **Annotation**: `$X` above each bar, colored green/red to match
- **Limit indicators**: thin horizontal `BarMark` at each category's limit level (using `yStart: limit * 0.98, yEnd: limit * 1.02`) in `.textPrimary` color
- Height: 200pt

**Per-category breakdown rows** (below chart):
- Each row: `[icon] [name] ... [$spent] / [$limit]`
- Spent amount colored green/red based on over-budget status
- Limit amount in secondary text

---

## Implementation Order

| Step | Feature | Size |
|------|---------|------|
| 1 | Feature 2: Data model — add `weeklyLimit` to UserCategory, CategoryPreference, backend | Small — additive field |
| 2 | Feature 3: CategorySettingsView — inline limit inputs + allocation footer | Medium — UI + binding |
| 3 | Feature 1: Global bar chart budget line + status callout | Medium — chart overlays |
| 4 | Feature 4: Category Budgets card on Insights tab | Medium — new chart section |

---

## Key Files

**Modified:**
- `BudgetBuddyBackend/db_models.py` — add `weekly_limit` to category pref entity
- `BudgetBuddyBackend/api/user.py` — add `weeklyLimit` to GET response
- `BudgetBuddy/BudgetBuddy/Models.swift` — add `weeklyLimit` to `CategoryPreference`
- `BudgetBuddy/BudgetBuddy/CategoryManager.swift` — add `weeklyLimit` to `UserCategory`, budget tracking properties, `setWeeklyLimit()` method
- `BudgetBuddy/BudgetBuddy/InsightsViewModel.swift` — add global budget limit properties, `CategoryBudgetEntry`, `categoryBudgetData`
- `BudgetBuddy/BudgetBuddy/Views/InsightsView.swift` — add budget overlay to bar chart, new `categoryBudgetsCard`, `budgetStatusColor`, `barColor(for:)`
- `BudgetBuddy/BudgetBuddy/Views/CategorySettingsView.swift` — inline limit inputs, `limitBinding(for:)`, allocation footer, `AddCategorySheet` weekly limit field, `iconDisplayNames`
- `BudgetBuddy/BudgetBuddy/Services/APIService.swift` — add `weeklyLimit` to `CategoryPreference` model
- `BudgetBuddy/Design/Theme.swift` — change `walletCard()` from `.clipShape()` to `.background()` to prevent chart label clipping

---

## Verification

1. **Global bar chart budget line**: Set a weekly budget of $100 in Profile → verify dashed red "Budget" line appears at $100/7 ≈ $14/day in Daily mode, $100 in Weekly mode. Bars exceeding the line are red, others are teal.
2. **Budget status callout**: With 2 of 5 days over budget → verify yellow text "2 of 5 days over budget". All over → red "All days over budget". None over → green "All days within budget".
3. **Target display**: Verify "Daily Target: $14" appears right-aligned next to "Daily Average: $X", colored with the same green/yellow/red scheme as the status text.
4. **No budget set**: Verify "Set a weekly budget to track spending limits" link appears instead, navigating to ProfileView.
5. **Per-category limits in Settings**: Set $50/wk on Food, $20/wk on Drink → verify inline display shows `$ 50 /wk` and `$ 20 /wk` next to each category.
6. **Budget allocation footer**: With $100 weekly budget and $70 allocated → verify green "$70 of $100 weekly budget allocated ($30 left)". Over-allocated → red with warning icon.
7. **Add category with limit**: Create new "Shopping" category with $30/wk limit → verify it saves and appears with the limit.
8. **Category Budgets chart**: Go to Insights → scroll to "Category Budgets" → verify bars for Food and Drink with green/red coloring, limit indicator lines, and "$X" annotations.
9. **Category budget status**: 1 of 2 categories over budget → yellow text. Edit Limits button navigates to CategorySettingsView.
10. **Per-category breakdown**: Below the chart, verify rows show "[icon] Food $42 / $50" with correct coloring.
11. **Empty state**: Remove all category limits → verify the chart card shows "Set weekly limits per category in Categories settings" with link.
12. **Slots remaining**: In Add Category sheet footer, verify "X of 4 custom category slots remaining" text.
