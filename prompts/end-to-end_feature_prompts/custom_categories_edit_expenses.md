# BudgetBuddy: Custom Categories, Editable Expenses & Cache Fixes

## Context

This branch (`categories-edit-expenses`) addresses several UX issues and feature requests: transactions can't be fully edited (only category/items), new transactions don't appear immediately, cache persists across account switches, categories are limited to 6 hardcoded options, and voice/receipt LLM responses sometimes fail to pre-select the correct category.

All changes are backward-compatible with the existing production Google Cloud Datastore database — no breaking entity changes, additive-only API responses, and safe defaults for all new fields.

---

## Feature 1: Editable Amount, Merchant, and Date on Transactions

Previously, `TransactionClassificationSheet` showed merchant, date, and amount as read-only text. Users could only change category and receipt items.

### Feature 1 — Backend

**`BudgetBuddyBackend/api/expenses.py`**

- Extend `PUT /transaction/<id>/classify` to accept optional `amount`, `merchantName`, `date` fields in the request body
- Apply them to the Datastore entity before `client.put(txn)` — works for both Plaid and Manual transactions
- Include updated values in the response's `ClassifiedTransactionInfo`

### Feature 1 — iOS

**`BudgetBuddy/BudgetBuddy/Models.swift`**

- Add `amount: Double?`, `merchantName: String?`, `date: String?` to `ClassifiedTransactionInfo`

**`BudgetBuddy/BudgetBuddy/Services/APIService.swift`**

- Add optional `amount`, `merchantName`, `date` params to `classifyTransaction()` method
- Include them in the JSON body only when non-nil

**`BudgetBuddy/BudgetBuddy/ExpensesViewModel.swift`**

- Update `classifyTransactionForSheet()` signature to accept optional `amount`, `merchantName`, `date`
- Pass new fields through to `apiService.classifyTransaction()` and `applyClassificationLocally()`
- Update `applyClassificationLocally()` to apply amount/merchant/date overrides to the local transaction copy

**`BudgetBuddy/BudgetBuddy/Views/ExpensesView.swift`**

- Add `@State` properties: `editedMerchant`, `editedAmount`, `editedDate` to `TransactionClassificationSheet`
- Replace read-only header with editable fields:
  - `TextField` for merchant name
  - `TextField` with `.keyboardType(.decimalPad)` for amount (with `$` prefix)
  - `DatePicker` (compact style) for date
  - Source badge section (voice/manual/receipt/plaid)
- Init parses ISO date string into `Date` for DatePicker
- Save button computes which fields actually changed and passes only changed values as optional overrides

---

## Feature 2: Immediate Cache Updates + Fix Pull-to-Refresh

### Problem A: New transactions don't appear immediately

After adding via voice/manual/receipt, `refreshWithRetry()` polled the API with exponential backoff waiting for Datastore consistency. Slow and unreliable.

### Solution A: Optimistic local insert

**Backend changes:**

- **`BudgetBuddyBackend/api/user.py`** — Expand `POST /user/transactions` response to return the full transaction object (matching the format from `GET /expenses`)
- **`BudgetBuddyBackend/api/receipt.py`** — Expand `POST /receipt/attach` response to include full transaction object

**iOS changes:**

- **`BudgetBuddy/BudgetBuddy/Models.swift`** — Update `SaveTransactionResponse` to include optional `transaction: ExpenseTransaction?`. Update `ReceiptAttachResponse` similarly.
- **`BudgetBuddy/BudgetBuddy/ExpensesViewModel.swift`** — Add `insertTransactionLocally(_ transaction: ExpenseTransaction)` that prepends to `allTransactions` (with duplicate guard) and calls `saveToCache()`
- **`BudgetBuddy/BudgetBuddy/VoiceTransactionViewModel.swift`** — Post `.transactionAdded` notification with the transaction object in `userInfo` after successful save
- **`BudgetBuddy/BudgetBuddy/ReceiptScanViewModel.swift`** — Same notification pattern after receipt attach
- **`BudgetBuddy/BudgetBuddy/Views/ExpensesView.swift`** — Replace `refreshWithRetry()` calls with `.onReceive(NotificationCenter.default.publisher(for: .transactionAdded))` that calls `viewModel.insertTransactionLocally(txn)`. Background `refresh()` still runs for eventual sync.

### Problem B: Pull-to-refresh auto-cancels

SwiftUI `.refreshable` cancels the async task if the view re-renders. Since `isLoading` toggles trigger re-render, this aborts the fetch.

### Solution B: Detached inner task

**`BudgetBuddy/BudgetBuddy/ExpensesViewModel.swift`**

```swift
func refresh() async {
    let task = Task { await fetchExpenses() }
    await task.value  // Inner task survives .refreshable cancellation
}
```

---

## Feature 3: Clear Cache on Sign Out / Account Switch

### Root Cause

`ContentView.swift` declares `@State private var expensesViewModel = ExpensesViewModel()`. The `.id(authManager.authToken)` modifier recreates child views but NOT the `@State` property on `ContentView`. So `expensesViewModel.allTransactions` retains the old user's data in memory even after `clearUserCache()` wipes UserDefaults.

### Solution

**`BudgetBuddy/BudgetBuddy/ExpensesViewModel.swift`**

- Add `clearData()` method that resets `allTransactions = []`, `weeksBack = 2`, `selectedFilter = .all`, and all other state

**`BudgetBuddy/BudgetBuddy/InsightsViewModel.swift`**

- Add similar `clearData()` method

**`BudgetBuddy/BudgetBuddy/Views/ContentView.swift`**

- Add `.onChange(of: authManager.authToken)` that calls `expensesViewModel.clearData()`, `insightsViewModel.clearData()`, and `CategoryManager.shared.clearData()` when the token changes
- On new token, also loads categories: `Task { await CategoryManager.shared.loadCategories() }`

---

## Feature 4: Custom User Categories

Users can add up to 4 custom categories (with emoji and reordering) in Settings. Custom categories appear in all pickers, filters, summary cards, badges, and charts. Backend auto-classification maps to user-specific categories.

### Feature 4 — Backend

**`BudgetBuddyBackend/db_models.py`**

- Extend `set_category_prefs()` to store `emoji` and `is_builtin` fields per category entity
- Add `get_user_custom_categories(user_id)` helper that returns custom category names for a user

**`BudgetBuddyBackend/api/user.py`**

- Update `GET /user/category-preferences/<user_id>` to return `emoji` and `isBuiltin` fields
- Update `PUT /user/category-preferences/<user_id>` to accept rich structure `[{name, emoji, isBuiltin}]` with validation (max 10 total, unique names, can't delete builtins)
- Add `DELETE /user/category-preferences/<user_id>/<category_name>?migrate_to=other` — migrates transactions to target category then deletes the preference entity
- Update `POST /user/parse-transaction` to accept optional `userId` — if provided, fetches custom categories and includes them in the LLM parsing prompt

**`BudgetBuddyBackend/services/classification_service.py`**

- Add `get_valid_categories_for_user(user_id)` helper — returns builtin + custom categories
- Add `_build_custom_category_context(user_id)` for LLM prompt injection
- Update `llm_classify_merchant()` and `llm_classify_merchants_batch()` to accept optional `user_id`, include custom categories in prompts, and validate against user-specific category lists

**`BudgetBuddyBackend/services/receipt_service.py`**

- `analyze_receipt()` accepts optional `custom_categories` parameter
- Includes custom category names in the Claude Vision prompt's valid category list

**`BudgetBuddyBackend/api/expenses.py`**

- Replace all `VALID_CATEGORIES` references with `get_valid_categories_for_user(user_id)`
- Make spending summary dynamic: keep existing `totalFood`/`totalDrink`/etc. keys for backward compat AND add a new `categoryTotals` dict that includes custom categories

**`BudgetBuddyBackend/api/receipt.py`**

- Pass custom categories to `analyze_receipt()` when `userId` is provided

### Feature 4 — iOS: CategoryManager

**New file: `BudgetBuddy/BudgetBuddy/CategoryManager.swift`**

`@Observable @MainActor` singleton managing all categories:

- `UserCategory` struct: `name`, `displayName`, `emoji`, `isBuiltin`, `displayOrder`
- 6 builtins: food, drink, groceries, transportation, entertainment, other
- Methods: `loadCategories()`, `saveCategories()`, `addCategory()`, `deleteCategory()`, `reorder()`, `clearData()`
- Helpers: `isValidCategory()`, `displayName(for:)`, `emoji(for:)`, `color(for:)`, `icon(for:)`
- Custom category colors from palette: `[.pink, .cyan, .mint, .indigo]` (assigned by index)
- `UserDefaults` cache for offline use
- Max 4 custom categories

### Feature 4 — iOS: CategorySettingsView

**New file: `BudgetBuddy/BudgetBuddy/Views/CategorySettingsView.swift`**

- Reorderable `List` with drag handles (edit mode always active)
- Built-in categories show "Built-in" label, not deletable
- Custom categories show "Custom" label, swipe-to-delete
- "Add Category" button (disabled at 4 custom) — presents `AddCategorySheet`
- `AddCategorySheet`: name TextField + emoji grid picker (24 common emojis)
- Saves on disappear and after mutations

**`BudgetBuddy/BudgetBuddy/Views/ProfileView.swift`**

- Add `categorySettingsSection` as a `NavigationLink` to `CategorySettingsView` between Notifications and Face ID sections

### Feature 4 — iOS: Update All Category Pickers and Filters

**`BudgetBuddy/BudgetBuddy/Models.swift`**

- Replace `ExpensesSummary` from 6 hardcoded totals to dynamic:
  ```swift
  struct ExpensesSummary {
      let categoryTotals: [String: Double]
      let totalUnclassified: Double
      var total: Double { categoryTotals.values.reduce(0, +) + totalUnclassified }
  }
  ```

**`BudgetBuddy/BudgetBuddy/ExpensesViewModel.swift`**

- Replace `ExpenseFilter` enum with a `Hashable` struct — `allFilters` computed from `CategoryManager.shared.categories`
- Update `transactions` computed property to filter by `selectedFilter.name`
- Update `summary` computed property to build `categoryTotals` from `CategoryManager`
- Update `isUnclassified()` to use `CategoryManager.shared.isValidCategory()` instead of hardcoded list

**`BudgetBuddy/BudgetBuddy/Views/ExpensesView.swift`**

- Filter pills: `ExpenseFilter.allCases` → `ExpenseFilter.allFilters`, `.rawValue` → `.displayName`
- Global category helpers (`normalizedItemCategory`, `categoryColor`, `categoryIcon`): delegate to `CategoryManager`
- `ExpensesSummaryCard` segments: dynamic from `CategoryManager.shared.categories` + unclassified
- `ExpenseTransactionRow` badge: uses `CategoryManager.shared.isValidCategory()` and `displayName(for:)`
- `TransactionClassificationSheet`:
  - `categories` computed property from `CategoryManager.shared.categories.map { $0.displayName }`
  - Init uses `CategoryManager.shared.isValidCategory()` for pre-selection
  - Category picker grid shows emoji (from `UserCategory.emoji`) instead of SF Symbols

**`BudgetBuddy/BudgetBuddy/Views/Wallet/TransactionConfirmationView.swift`**

- Replace hardcoded `categories` constant with computed property from `CategoryManager`

**`BudgetBuddy/BudgetBuddy/Views/Components/TransactionItemsSection.swift`**

- Replace hardcoded `allCategories` constant with computed property from `CategoryManager`

**`BudgetBuddy/BudgetBuddy/Views/Receipt/ReceiptLineItemsView.swift`**

- Replace hardcoded `allCategories` constant with computed property from `CategoryManager`

**`BudgetBuddy/BudgetBuddy/Services/APIService.swift`**

- Update `getCategoryPreferences()` to return `[CategoryPreference]` with `emoji` and `isBuiltin`
- Update `updateCategoryPreferences()` to accept `[[String: Any]]` with rich structure
- Add `deleteCustomCategory(userId:categoryName:migrateTo:)`
- Update `parseTransaction()` to accept optional `userId` parameter

**`BudgetBuddy/BudgetBuddy/VoiceTransactionViewModel.swift`**

- Pass `userId` in `parseTranscription()` API call so backend includes custom categories in LLM prompt

**`BudgetBuddy/BudgetBuddy/Views/ContentView.swift`**

- Load `CategoryManager.shared.loadCategories()` on app launch (after auth restore)
- Clear and reload on account switch

---

## Feature 5: Fix Category Pre-selection for Voice/Receipt

### Root Cause

`TransactionConfirmationView` checks `categories.contains(category)` where `categories` is title-case `["Food", ...]` but the LLM sometimes returns lowercase `"food"`. Case mismatch causes the check to fail, leaving `selectedCategory = ""`.

### Solution

**`BudgetBuddy/BudgetBuddy/VoiceTransactionViewModel.swift`**

- Normalize parsed category: `txn.category = parsed.category?.capitalized`

**`BudgetBuddy/BudgetBuddy/Views/Wallet/TransactionConfirmationView.swift`**

- Use case-insensitive matching in `populateFromViewModel()`:
  ```swift
  if let category = viewModel.transaction.category,
     let match = categories.first(where: { $0.caseInsensitiveCompare(category) == .orderedSame }) {
      selectedCategory = match
  }
  ```

---

## Implementation Order

| Step | Feature | Size |
|------|---------|------|
| 1 | Feature 5: Fix category pre-selection | Smallest — bug fix, no new UI |
| 2 | Feature 3: Clear cache on sign out | Small — state reset |
| 3 | Feature 2: Optimistic insert + refresh fix | Medium — backend response expansion + client-side insert |
| 4 | Feature 1: Editable transaction fields | Medium — new editable UI + backend support |
| 5 | Feature 4: Custom categories | Largest — new files, touches most existing files |

---

## Key Files

**Modified:**
- `BudgetBuddyBackend/api/expenses.py`
- `BudgetBuddyBackend/api/user.py`
- `BudgetBuddyBackend/api/receipt.py`
- `BudgetBuddyBackend/services/classification_service.py`
- `BudgetBuddyBackend/services/receipt_service.py`
- `BudgetBuddyBackend/db_models.py`
- `BudgetBuddy/BudgetBuddy/Models.swift`
- `BudgetBuddy/BudgetBuddy/Services/APIService.swift`
- `BudgetBuddy/BudgetBuddy/ExpensesViewModel.swift`
- `BudgetBuddy/BudgetBuddy/InsightsViewModel.swift`
- `BudgetBuddy/BudgetBuddy/VoiceTransactionViewModel.swift`
- `BudgetBuddy/BudgetBuddy/Views/ExpensesView.swift`
- `BudgetBuddy/BudgetBuddy/Views/ContentView.swift`
- `BudgetBuddy/BudgetBuddy/Views/ProfileView.swift`
- `BudgetBuddy/BudgetBuddy/Views/Wallet/TransactionConfirmationView.swift`
- `BudgetBuddy/BudgetBuddy/Views/Components/TransactionItemsSection.swift`
- `BudgetBuddy/BudgetBuddy/Views/Receipt/ReceiptLineItemsView.swift`

**Created:**
- `BudgetBuddy/BudgetBuddy/CategoryManager.swift`
- `BudgetBuddy/BudgetBuddy/Views/CategorySettingsView.swift`

---

## Verification

1. **Feature 5**: Add voice transaction saying "ten dollars at Starbucks for coffee" → verify category pre-selects "Drink" (or "Food"). Test with receipt scan.
2. **Feature 3**: Sign out → sign into different account → verify expenses screen is empty, then loads new user's data. Verify categories also reset.
3. **Feature 2**: Add voice transaction → verify it appears immediately in expenses list without polling. Pull down to refresh → verify spinner completes and data refreshes without canceling.
4. **Feature 1**: Tap a transaction → edit merchant name, amount, date → save → verify changes persist after pull-to-refresh.
5. **Feature 4**:
   - Settings → Categories → add custom category "Coffee" with ☕ emoji → verify it appears in all category pickers (classification sheet, voice confirmation, receipt review, item-level picker)
   - Filter pills on Expenses tab show the new category
   - Summary card shows spending for the custom category
   - Voice transaction → verify LLM can classify into custom category
   - Delete custom category → verify transactions migrate to "Other"
