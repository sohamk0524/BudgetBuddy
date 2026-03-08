# BudgetBuddy: Groceries Category, Line Items, Voice Multi-Transaction & UX Polish

## Context

This branch (`groceries-and-items-fixes`) adds first-class support for grocery spending, enables editable line items on transactions (both receipt-scanned and voice-logged), improves the receipt scanning loading experience, and upgrades the voice transaction flow to support multiple transactions in a single recording. It also fixes several data integrity bugs.

---

## Feature 1: Groceries as a First-Class Category

Groceries was previously lumped into "Other". It is now a distinct category with its own icon, color, and summary line.

### Feature 1 — Backend

**`BudgetBuddyBackend/api/expenses.py`**

- Add `"groceries"` to `VALID_CATEGORIES`
- Add `"totalGroceries"` to the GET `/expenses` summary response

**`BudgetBuddyBackend/api/user.py`**

- Add `"groceries"` to valid categories in `POST /user/transactions` and `PUT /user/transactions/<id>`

### Feature 1 — iOS

**`BudgetBuddy/BudgetBuddy/Models.swift`**

- Add `totalGroceries: Double` to `ExpensesSummary`; include it in the `total` computed property
- Add `groceries` case to the `ExpenseCategory` enum

**`BudgetBuddy/BudgetBuddy/ExpensesViewModel.swift`**

- Add `"groceries"` to all `knownCategories` arrays
- Include `totalGroceries` in the summary totals dict

**`BudgetBuddy/BudgetBuddy/Views/ExpensesView.swift`**

- Add `"Groceries"` row to `ExpensesSummaryCard` with `.green` color
- Add `case "groceries"` to `categoryColor()` (`.green`) and `categoryIcon()` (`"cart.fill"`)
- Add `"groceries"` to the `known` category badge array in `ExpenseTransactionRow`
- Add `"Groceries"` to the category picker in `TransactionClassificationSheet`

**`BudgetBuddy/BudgetBuddy/Views/Receipt/ReceiptLineItemsView.swift`**

- Add `"groceries"` to `allCategories` for item-level classification

---

## Feature 2: Editable Line Items on Transactions

Both receipt-scanned and voice-logged transactions can now carry per-item line items. Items are editable (add/remove/recategorize) in `ReceiptLineItemsView` and in the `TransactionClassificationSheet` (the detail sheet opened from the expenses list).

### Feature 2 — Backend

**`BudgetBuddyBackend/api/expenses.py`**

- **New `PUT /transaction/<id>/receipt-items`** — replaces or appends items on any transaction (Plaid or manual). Accepts `{ "items": [...], "replace": bool }`. Recomputes `sub_category` from dominant item spend by value. Returns `{ success, itemCount, subCategory }`.
- **New `DELETE /transaction/<id>`** — deletes a transaction by Datastore key (tries both `Transaction` and `ManualTransaction` kinds).
- `_parse_receipt_items()` normalizes stored items: renames `"category"` → `"classification"` so the iOS `ReceiptLineItem` decoder always succeeds.

**`BudgetBuddyBackend/api/user.py` — `POST /user/transactions`**

- Accept optional `receiptItems` array; normalise each item's key (`"classification"` or `"category"` → stored as `"classification"`); serialise to JSON string; recompute `sub_category` from dominant item spend if items are provided.

### Feature 2 — iOS Models

**`BudgetBuddy/BudgetBuddy/Models.swift`** and **`ReceiptLineItemsView.swift`**

- New `EditableReceiptItem` struct (`id: UUID`, `name`, `price`, `category`) — lives in `ReceiptLineItemsView.swift`. Has `init(from: ReceiptLineItem)` and `toReceiptLineItem()` converters. `isDiscount: Bool` derived from `price < 0`.
- `AddReceiptItemsResponse` struct (`success`, `itemCount`, `subCategory?`)
- `VoiceTransaction` gains an `items: [EditableReceiptItem]` field
- `SaveTransactionRequest` gains a `receiptItems: [[String: String]]?` field
- `ReceiptLineItem.category` changed from `let` → `var`

### Feature 2 — iOS APIService

**`BudgetBuddy/BudgetBuddy/APIService.swift`**

- **`addReceiptItems(transactionId:items:replace:)`** → `PUT /transaction/<id>/receipt-items`
- **`deleteTransaction(transactionId:)`** → `DELETE /transaction/<id>`

### Feature 2 — Shared Component

**New `BudgetBuddy/BudgetBuddy/Views/Components/TransactionItemsSection.swift`**

- Reusable `TransactionItemsSection(items: Binding<[EditableReceiptItem]>, editable: Bool = true)` view
- When `editable: true`: add-item row, swipe-to-delete, inline name/price/category editing per row
- When `editable: false`: read-only display (used in expense detail context)
- Used by both `ReceiptLineItemsView` and `TransactionClassificationSheet`

### Feature 2 — iOS ExpensesViewModel

**`BudgetBuddy/BudgetBuddy/ExpensesViewModel.swift`**

- **`addItemsToTransaction(transactionId:items:replace:)`** — calls `APIService.addReceiptItems`, then applies the returned `subCategory` locally via `applyClassificationLocally`
- **`deleteTransaction(transactionId:)`** — calls `APIService.deleteTransaction`, removes from `allTransactions` in memory

### Feature 2 — TransactionClassificationSheet

**`BudgetBuddy/BudgetBuddy/Views/ExpensesView.swift`**

- `@State private var localItems: [EditableReceiptItem]` — initialised from `transaction.receiptItems`, tracked via `localItemsModified` flag
- Embeds `TransactionItemsSection(items: $localItems)` below the category picker
- On Save: if items were modified, calls `viewModel.addItemsToTransaction(..., replace: true)` before classifying
- **New Delete Transaction button** — `.destructive` confirmation dialog, calls `viewModel.deleteTransaction`, dismisses on success
- Notes line hidden for receipt-sourced transactions (merchant shown in header instead)

---

## Feature 3: ReceiptLineItemsView Redesign

**`BudgetBuddy/BudgetBuddy/Views/Receipt/ReceiptLineItemsView.swift`**

Full rewrite with editable items and improved UX:

- `onConfirm` callback now includes `items: [EditableReceiptItem]` (was category+date+merchant only)
- Header card split into 3 separate rows (Store / Total / Date) with dividers between them
- Total row is auto-computed from `itemsSum`; tapping a lock icon lets user override manually
- Tax row shown when `total > itemsSum` (reflects tax not captured as line items)
- Category picker auto-selects the dominant category by item spend (not hardcoded to "Food")
- Embeds `TransactionItemsSection(items: $allItems, editable: true)` — full inline item editing
- `EditableReceiptItem` defined at top of this file (used project-wide via `TransactionItemsSection`)

**`BudgetBuddy/BudgetBuddy/ReceiptScanViewModel.swift`**

- `confirmAndAttach(category:items:date:merchant:)` — passes edited items through to API; builds `finalResult` with `items.map { $0.toReceiptLineItem() }`
- New `analysisIsComplete: Bool` flag — set when backend returns, observed by `ReceiptLoadingView` to "fast-drain" remaining animation steps; `finishAnalysis()` called by the view to transition to `.reviewed`

**`BudgetBuddy/BudgetBuddy/Views/Receipt/ReceiptScanView.swift`**

- Animated `ReceiptLoadingView` replaces the plain spinner during analysis
- `ReceiptLoadingView(isBackendDone:onAllStepsDone:)` shows 4 sequential steps (Scanning image → Reading merchant & date → Extracting line items → Categorizing expenses) with checkmark animations; fast-drains once backend is done, then calls `onAllStepsDone`
- `.attaching` state keeps a simple spinner (it's a fast DB write)

---

## Feature 4: Voice Transaction — Multi-Transaction Flow

A single voice recording can now produce multiple transactions (one per merchant). The confirmation UI is fully redesigned to match the receipt scan sheet, and auto-stops after 1.5 s of silence.

### Feature 4 — Backend

**`BudgetBuddyBackend/api/user.py` — `POST /user/parse-transaction`**

- Injects today's date into the LLM prompt
- LLM instructions updated: group by merchant, return `{ "transactions": [...] }`
- Each transaction object: `store`, `amount`, `category` (Food/Drink/Groceries/Transportation/Entertainment/Other), `date` (YYYY-MM-DD, defaults to today), `notes`, `items[]`
- Each item: `name`, `price`, `classification` (lowercase)
- `_fallback()` returns a single empty-transaction array on parse/network error

**`BudgetBuddyBackend/api/user.py` — `PUT /user/transactions/<id>`**

- New endpoint for updating a previously saved transaction (used when the user presses Back in the multi-step confirmation flow to re-edit)

**`BudgetBuddyBackend/db_models.py`**

- `get_manual_transactions(user_id, limit=0)` — default limit changed from `50` → `0` (no silent data loss for users with >50 transactions)

### Feature 4 — iOS Models

**`BudgetBuddy/BudgetBuddy/Models.swift`**

```swift
struct ParsedTransactionGroupResponse: Codable {
    let transactions: [ParsedTransactionWithItems]
}
struct ParsedTransactionWithItems: Codable {
    let amount: Double?; let category: String?; let store: String?
    let date: String?; let notes: String?; let items: [ParsedItem]?
}
struct ParsedItem: Codable {
    let name: String; let price: Double; let classification: String
}
```

### Feature 4 — iOS APIService

- `parseTransaction` return type changed from `ParsedTransactionResponse` → `ParsedTransactionGroupResponse`
- **`updateManualTransaction(transactionId:request:)`** → `PUT /user/transactions/<id>`

### Feature 4 — iOS SpeechRecognizer

**`BudgetBuddy/BudgetBuddy/Services/SpeechRecognizer.swift`**

- `var onSilenceDetected: (() -> Void)?` + `var silenceTimeout: TimeInterval = 1.5`
- Each transcription update cancels the previous `DispatchWorkItem` and schedules a fresh 1.5 s work item
- Work item cancelled in `stopRecording()`

### Feature 4 — VoiceTransactionViewModel

**`BudgetBuddy/BudgetBuddy/VoiceTransactionViewModel.swift`**

- `pendingTransactions: [ParsedTransactionWithItems]`, `currentIndex: Int`, `savedTransactionIds: [Int: Int]`
- `saveTransaction()`: if index already saved → PUT (update), else → POST (create); advances index or transitions to `.success`
- `goBack()`: decrement index (allows re-editing)
- `discardCurrent()`: remove from array, adjust index
- Item serialisation uses `"classification"` key (not `"category"`)
- `onSilenceDetected` wired to call `stopRecording()`

### Feature 4 — TransactionConfirmationView (full redesign)

**`BudgetBuddy/BudgetBuddy/Views/Wallet/TransactionConfirmationView.swift`**

- Nav title: `"Transaction X of N"` in multi-transaction mode
- Leading toolbar Back button (only when index > 0) — saves local edits before navigating back
- Header card: Store / Amount / Date rows separated by `Divider`
- Horizontal scrollable category chip picker (capsule style); red `"— required"` label + border on failed submit
- Discard button (multi only) with `.confirmationDialog` confirmation
- Pinned bottom button: `"Save & Next"` / `"Save & Finish"` / `"Save"` depending on context; `ProgressView` while `.saving`
- `onChange(of: viewModel.currentIndex)` repopulates local fields when Back is pressed
- Sheet detent: `.large` (was `.medium`)

### Feature 4 — VoiceTransactionFlowView

**`BudgetBuddy/BudgetBuddy/Views/Wallet/VoiceTransactionFlowView.swift`**

- `@Bindable var viewModel` → `var viewModel` (no bindings needed at this level)
- `Group { switch }` replaced with `@ViewBuilder private var currentScreen: some View` (fixes Swift type-inference error with associated-value enums)

### Feature 4 — VoiceTransactionSuccessView

**`BudgetBuddy/BudgetBuddy/Views/Wallet/VoiceTransactionSuccessView.swift`**

- Accepts `transactionCount: Int`
- Auto-dismisses after 1.5 s
- Multi: "All Saved! / N transactions logged." Single: "Transaction Saved!"

---

## Feature 5: Expenses History & Consistency Fixes

**`BudgetBuddy/BudgetBuddy/ExpensesViewModel.swift`**

### `loadPreviousWeek()` — 4-week / 10-item advance

Each tap advances up to 4 weeks, stopping early once 10+ new transactions appear:

```swift
let maxNewItems = 10; let maxWeeksToAdd = 4; var weeksAdded = 0
while weeksAdded < maxWeeksToAdd && canLoadMore {
    weeksBack += 1; weeksAdded += 1
    // fetch; break if count delta >= maxNewItems
}
```

### `refreshWithRetry()` — Datastore eventual consistency

After saving a transaction, retry fetching up to 3 times until count increases:

```swift
func refreshWithRetry() async {
    let countBefore = allTransactions.count
    await fetchExpenses()
    if allTransactions.count > countBefore { return }
    for delay: UInt64 in [1_000_000_000, 2_000_000_000, 4_000_000_000] {
        try? await Task.sleep(nanoseconds: delay)
        await fetchExpenses()
        if allTransactions.count > countBefore { return }
    }
}
```

Used after both voice saves and receipt attaches.

---

## Implementation Order

| Step | What | File(s) |
|------|------|---------|
| 1 | Add `groceries` to backend `VALID_CATEGORIES` and summary | `api/expenses.py`, `api/user.py` |
| 2 | New backend endpoints: receipt-items PUT, transaction DELETE | `api/expenses.py` |
| 3 | Parse-transaction multi-response + PUT update endpoint | `api/user.py` |
| 4 | `get_manual_transactions` no-limit fix | `db_models.py` |
| 5 | iOS: `EditableReceiptItem`, `AddReceiptItemsResponse`, updated models | `Models.swift`, `ReceiptLineItemsView.swift` |
| 6 | iOS: `TransactionItemsSection` shared component | `Views/Components/TransactionItemsSection.swift` |
| 7 | iOS: ReceiptLineItemsView redesign (editable items, auto-total, dominant category) | `ReceiptLineItemsView.swift` |
| 8 | iOS: ReceiptScanView animated loading + `analysisIsComplete` flow | `ReceiptScanView.swift`, `ReceiptScanViewModel.swift` |
| 9 | iOS: Groceries added to all category arrays/colors/icons | `ExpensesView.swift`, `ExpensesViewModel.swift` |
| 10 | iOS: TransactionClassificationSheet — item editing + delete button | `ExpensesView.swift` |
| 11 | iOS: APIService new methods | `APIService.swift` |
| 12 | iOS: ExpensesViewModel — `deleteTransaction`, `addItemsToTransaction`, `refreshWithRetry`, `loadPreviousWeek` | `ExpensesViewModel.swift` |
| 13 | iOS: Silence detection in SpeechRecognizer | `SpeechRecognizer.swift` |
| 14 | iOS: VoiceTransactionViewModel multi-transaction state machine | `VoiceTransactionViewModel.swift` |
| 15 | iOS: TransactionConfirmationView redesign | `TransactionConfirmationView.swift` |
| 16 | iOS: VoiceTransactionFlowView `@ViewBuilder` refactor | `VoiceTransactionFlowView.swift` |
| 17 | iOS: VoiceTransactionSuccessView auto-dismiss + count | `VoiceTransactionSuccessView.swift` |

---

## Key Files Modified / Created

**Modified:**

- `BudgetBuddyBackend/api/expenses.py` — Groceries category, receipt-items PUT, transaction DELETE, item key normalisation
- `BudgetBuddyBackend/api/user.py` — multi-transaction parse, receipt items on save, PUT update endpoint, Groceries category
- `BudgetBuddyBackend/services/receipt_service.py` — consistent item key handling
- `BudgetBuddyBackend/db_models.py` — `get_manual_transactions` default limit → 0
- `BudgetBuddy/BudgetBuddy/Models.swift` — `EditableReceiptItem`, `AddReceiptItemsResponse`, `ParsedTransactionGroupResponse`, `ParsedTransactionWithItems`, `ParsedItem`, `totalGroceries`, updated `VoiceTransaction`/`SaveTransactionRequest`
- `BudgetBuddy/BudgetBuddy/APIService.swift` — `parseTransaction` return type, `updateManualTransaction`, `addReceiptItems`, `deleteTransaction`
- `BudgetBuddy/BudgetBuddy/ReceiptScanViewModel.swift` — `analysisIsComplete`, `finishAnalysis()`, items passed through `confirmAndAttach`
- `BudgetBuddy/BudgetBuddy/Services/SpeechRecognizer.swift` — silence detection
- `BudgetBuddy/BudgetBuddy/VoiceTransactionViewModel.swift` — multi-transaction state machine
- `BudgetBuddy/BudgetBuddy/ExpensesViewModel.swift` — Groceries, `deleteTransaction`, `addItemsToTransaction`, `refreshWithRetry`, `loadPreviousWeek` 4-week/10-item
- `BudgetBuddy/BudgetBuddy/Views/ExpensesView.swift` — Groceries color/icon/badge, item editing in classification sheet, delete button, `refreshWithRetry`
- `BudgetBuddy/BudgetBuddy/Views/Receipt/ReceiptLineItemsView.swift` — full redesign with editable items
- `BudgetBuddy/BudgetBuddy/Views/Receipt/ReceiptScanView.swift` — animated loading view
- `BudgetBuddy/BudgetBuddy/Views/Wallet/TransactionConfirmationView.swift` — full redesign
- `BudgetBuddy/BudgetBuddy/Views/Wallet/VoiceTransactionFlowView.swift` — `@ViewBuilder` refactor
- `BudgetBuddy/BudgetBuddy/Views/Wallet/VoiceTransactionSuccessView.swift` — count + auto-dismiss

**Created:**

- `BudgetBuddy/BudgetBuddy/Views/Components/TransactionItemsSection.swift`

---

## Verification

1. **Groceries**: Log a grocery transaction → appears with green cart icon; shows in Groceries row of summary
2. **Receipt items**: Scan a receipt → items are editable before confirming; items persist and show in the expense detail sheet
3. **Item editing in sheet**: Open any receipt-attached transaction → edit/add/delete items → save → sub-category updates to dominant item type
4. **Delete transaction**: Open any transaction detail → Delete → transaction removed from list immediately
5. **Receipt loading animation**: Scan a receipt → 4 animated steps appear; last step completes and transitions automatically when backend returns
6. **Voice multi-transaction**: Say "I spent $12 at Starbucks and $40 at Trader Joe's" → two confirmation sheets appear sequentially; Back button re-opens the first for editing
7. **Voice silence auto-stop**: Begin recording and stop talking → recording stops automatically after ~1.5 s; manual stop button still works
8. **Voice line items**: Say "I got a latte for $5 and a muffin for $7 at Blue Bottle" → items appear in the confirmation sheet and are saved with the transaction
9. **Load history**: Tap "Load Previous Week" → advances up to 4 weeks or stops at 10 new items, whichever comes first
10. **No data cap**: Users with >50 manual transactions see all of them
11. **Post-save refresh**: New transactions appear in the list within a few seconds after saving (retry handles Datastore propagation delay)
