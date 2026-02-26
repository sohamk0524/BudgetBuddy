# BudgetBuddy: Expenses Screen

## Context

BudgetBuddy has Plaid-linked transactions stored in the `Transaction` entity in Datastore. This feature adds a full **Expenses tab** that lets users view, filter, and classify their transactions into **Essential** and **Fun Money** buckets — the two core categories from their spending plan. Classification can happen via:
- Manual swipe (Tinder-style card deck for unclassified transactions)
- Tap-to-edit on any transaction row
- AI auto-classify (batch LLM inference for all unclassified merchants)
- Automatic pre-seeded defaults (for unambiguous Plaid categories like rent, utilities, loans)
- Auto-promotion from confidence threshold (merchant is auto-applied after 3 consistent user classifications)

---

## Phase 1: Backend — Database Models

### 1A. Transaction Entity Updates
**File:** `BudgetBuddyBackend/db_models.py`

The existing `Transaction` entity needs the following additional fields if not already present:
- `sub_category` — string: `"essential"`, `"fun_money"`, `"split"`, or `None` (unclassified)
- `essential_ratio` — float (0.0–1.0): portion of amount that counts as Essential when `sub_category = "split"`
- `merchant_name` — string: normalized merchant name from Plaid (used for merchant-level classification grouping)

### 1B. New: MerchantClassification Entity
**File:** `BudgetBuddyBackend/db_models.py`

New Datastore kind `MerchantClassification` with helper functions:
- Fields: `user_id`, `merchant_name` (normalized), `classification` (`"essential"` / `"fun_money"` / `"split"`), `essential_ratio` (float), `classification_count` (int, tracks how many times user confirmed), `is_user_confirmed` (bool), `created_at`, `updated_at`
- Helpers:
  - `get_merchant_classification(user_id, merchant_name)` → single entity or None
  - `get_merchant_classifications_for_user(user_id)` → list
  - `upsert_merchant_classification(user_id, merchant_name, classification, essential_ratio, increment_count, confirmed)` → upserts

### 1C. New: DeviceToken Entity
**File:** `BudgetBuddyBackend/db_models.py`

For push notification support (future use):
- Fields: `user_id`, `device_token` (string), `platform` (`"apns"` / `"fcm"`), `is_active` (bool), `created_at`, `updated_at`
- Helpers: `get_active_device_tokens(user_id)`, `get_device_token(user_id, token)`, `upsert_device_token(user_id, token, platform)`

---

## Phase 2: Backend — Classification Service

**New file:** `BudgetBuddyBackend/services/classification_service.py`

### 2A. Constants and Pre-Seeded Defaults

```python
CONFIDENCE_THRESHOLD = 3  # auto-apply merchant classification after this many consistent votes
```

`PRE_SEEDED_DEFAULTS` — dict mapping Plaid `detailed` category strings → `(classification, essential_ratio)` for unambiguous essentials:
- Rent/mortgage, utilities, loan payments, medical/dental/pharmacy, insurance, education/tuition, childcare → `("essential", 1.0)`

`PRIMARY_CATEGORY_DEFAULTS` — fallback by Plaid `primary` category:
- `"INCOME"` → `("essential", 1.0)`
- `"TRANSFER_IN"` / `"TRANSFER_OUT"` → `("essential", 1.0)`
- `"LOAN_PAYMENTS"` → `("essential", 1.0)`

### 2B. Classification Priority Chain

`classify_transaction(transaction, user_id)` — applies classifications in priority order:

1. **User MerchantClassification** — if `get_merchant_classification(user_id, merchant_name)` exists and `is_user_confirmed`, apply it
2. **Pre-seeded detailed** — check `PRE_SEEDED_DEFAULTS[transaction.detailed_category]`
3. **Pre-seeded primary** — check `PRIMARY_CATEGORY_DEFAULTS[transaction.primary_category]`
4. **LLM inference** — call `llm_classify_merchant()`, store result as unconfirmed MerchantClassification
5. **Unclassified** — leave `sub_category = None`

### 2C. LLM Classification

`llm_classify_merchant(merchant_name, user_id, category_hint)` — single inference:
- Builds prompt with merchant name, Plaid category, and user financial context (income, goals, occupation)
- Calls `claude-sonnet-4-5-20250929` via Anthropic SDK
- Returns `{"classification": "essential"|"fun_money"|"split", "essential_ratio": float, "confidence": float}`
- Stores result as unconfirmed `MerchantClassification`

`llm_classify_merchants_batch(merchant_list, user_id)` — batch inference for up to 20 merchants:
- Single LLM call with all merchants as JSON array in prompt
- Returns validated JSON array of classification objects
- Used by the auto-classify endpoint

`_get_user_classification_context(user_id)` — builds a brief user context string from their `FinancialProfile` (income, occupation, primary goal, financial personality) to improve LLM accuracy.

### 2D. Retroactive Reclassification

`retroactively_reclassify(user_id, merchant_name, classification, essential_ratio)`:
- Fetches all `Transaction` entities for user matching normalized merchant name
- Updates each one's `sub_category` and `essential_ratio`
- Used when a user confirms a merchant-level classification

`classify_new_transactions(transactions, user_id)` — batch wrapper calling `classify_transaction` for each new transaction.

### 2E. Auto-Confidence Promotion

In `classify_transaction` (and the PUT endpoint): after each user vote on a transaction, check if the merchant's `classification_count >= CONFIDENCE_THRESHOLD` and all votes are consistent. If so, set `is_user_confirmed = True` and call `retroactively_reclassify`.

---

## Phase 3: Backend — API Endpoints

**New file:** `BudgetBuddyBackend/api/expenses.py`
**Register as blueprint:** `expenses_bp` with prefix `/expenses` in `main.py`

### Endpoint Reference

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/expenses/<user_id>` | Paginated expenses list with summary |
| POST | `/merchant/classify` | Classify all transactions for a merchant |
| PUT | `/transaction/<transaction_id>/classify` | Classify a single transaction |
| GET | `/merchant/classifications/<user_id>` | List all merchant classifications |
| GET | `/expenses/unclassified/<user_id>` | Fetch up to 10 unclassified transactions sorted by impact |
| POST | `/expenses/auto-classify/<user_id>` | LLM batch-classify all unclassified merchants |
| POST | `/device/register` | Register push notification device token |
| POST | `/device/unregister` | Unregister push notification device token |

### 3A. GET `/expenses/<user_id>`

Query params: `page` (int, default 1), `limit` (int, default 20), `sub_category` (filter string)

Response:
```json
{
  "transactions": [ { ...ExpenseTransaction fields... } ],
  "summary": {
    "totalSpending": 1250.00,
    "essentialTotal": 800.00,
    "funMoneyTotal": 300.00,
    "splitTotal": 50.00,
    "unclassifiedTotal": 100.00,
    "essentialCount": 12,
    "funMoneyCount": 8,
    "splitCount": 1,
    "unclassifiedCount": 3
  },
  "hasMore": true,
  "page": 1
}
```

On first load, perform **lazy backfill**: for any transaction with `sub_category = None`, run `classify_transaction` to attempt auto-classification before returning the page.

### 3B. POST `/merchant/classify`

Body: `{ "user_id": str, "merchant_name": str, "classification": str, "essential_ratio": float }`

- Upserts `MerchantClassification` with `is_user_confirmed = True`
- Calls `retroactively_reclassify` to update all matching transactions
- Returns updated `MerchantClassification` info

### 3C. PUT `/transaction/<transaction_id>/classify`

Body: `{ "user_id": str, "sub_category": str, "essential_ratio": float }`

- Updates the single transaction
- Increments merchant classification vote count
- If `classification_count >= CONFIDENCE_THRESHOLD`, auto-promote and retroactively reclassify
- Returns updated transaction + whether merchant was auto-promoted

### 3D. GET `/expenses/unclassified/<user_id>`

Returns up to 10 unclassified transactions sorted by **round-robin merchant impact** (highest-spend merchant first, one transaction per merchant to show variety):
```json
{
  "transactions": [ { ...UnclassifiedTransactionItem fields... } ],
  "totalUnclassifiedCount": 47
}
```

### 3E. POST `/expenses/auto-classify/<user_id>`

- Finds all unclassified transactions grouped by merchant (up to 20 distinct merchants)
- Calls `llm_classify_merchants_batch`
- Applies results via `retroactively_reclassify` for each merchant
- Returns count of merchants and transactions classified

---

## Phase 4: Frontend — Models

**File:** `BudgetBuddy/BudgetBuddy/Models.swift`

Add the following structs (after existing Plaid models):

```swift
struct ExpenseTransaction: Codable, Identifiable {
    let id: String
    let merchantName: String
    let amount: Double
    let date: String
    let primaryCategory: String
    let detailedCategory: String
    let subCategory: String?      // "essential", "fun_money", "split", nil
    let essentialRatio: Double?   // 0.0–1.0 when subCategory == "split"
    let accountId: String
}

struct ExpensesSummary: Codable {
    let totalSpending: Double
    let essentialTotal: Double
    let funMoneyTotal: Double
    let splitTotal: Double
    let unclassifiedTotal: Double
    let essentialCount: Int
    let funMoneyCount: Int
    let splitCount: Int
    let unclassifiedCount: Int
}

struct ExpensesResponse: Codable {
    let transactions: [ExpenseTransaction]
    let summary: ExpensesSummary
    let hasMore: Bool
    let page: Int
}

struct MerchantClassificationInfo: Codable {
    let merchantName: String
    let classification: String
    let essentialRatio: Double
    let classificationCount: Int
    let isUserConfirmed: Bool
}

struct ClassifyMerchantResponse: Codable {
    let success: Bool
    let merchantClassification: MerchantClassificationInfo
    let transactionsUpdated: Int
}

struct ClassifyTransactionResponse: Codable {
    let success: Bool
    let transaction: ExpenseTransaction
    let merchantAutoPromoted: Bool
}

struct UnclassifiedTransactionItem: Codable, Identifiable {
    let id: String
    let merchantName: String
    let amount: Double
    let date: String
    let primaryCategory: String
    let detailedCategory: String
    let totalMerchantSpend: Double
}

struct UnclassifiedMerchant: Codable {
    let transactions: [UnclassifiedTransactionItem]
    let totalUnclassifiedCount: Int
}

struct AutoClassifyResponse: Codable {
    let success: Bool
    let merchantsClassified: Int
    let transactionsClassified: Int
}
```

---

## Phase 5: Frontend — API Service

**File:** `BudgetBuddy/BudgetBuddy/APIService.swift`

Add these methods following the existing `actor APIService` pattern:

```swift
func getExpenses(userId: String, page: Int, limit: Int, subCategory: String?) async throws -> ExpensesResponse
func classifyMerchant(userId: String, merchantName: String, classification: String, essentialRatio: Double) async throws -> ClassifyMerchantResponse
func classifyTransaction(transactionId: String, userId: String, subCategory: String, essentialRatio: Double) async throws -> ClassifyTransactionResponse
func getUnclassifiedTransactions(userId: String) async throws -> UnclassifiedMerchant
func autoClassifyExpenses(userId: String) async throws -> AutoClassifyResponse
```

All methods use the existing `baseURL + "/expenses/..."` pattern with `authToken` header.

---

## Phase 6: Frontend — ExpensesViewModel

**File:** `BudgetBuddy/BudgetBuddy/ExpensesViewModel.swift`

```swift
@Observable @MainActor
class ExpensesViewModel {
    // Paginated transaction list state
    var transactions: [ExpenseTransaction] = []
    var summary: ExpensesSummary? = nil
    var hasMore: Bool = false
    var currentPage: Int = 1
    var selectedFilter: String? = nil   // nil = all, "essential", "fun_money", "split", "unclassified"
    var isLoading: Bool = false
    var error: String? = nil

    // Swipe classification state
    var unclassifiedTransactions: [UnclassifiedTransactionItem] = []
    var totalUnclassifiedCount: Int = 0
    var currentClassifyIndex: Int = 0
    var isAutoClassifying: Bool = false
    var autoClassifyResult: String? = nil

    // Sheet state
    var selectedTransaction: ExpenseTransaction? = nil
    var showClassifySheet: Bool = false
    var showSplitSheet: Bool = false
    var splitTransaction: UnclassifiedTransactionItem? = nil
}
```

Key methods:
- `fetchExpenses()` — fetches page 1 with current filter, resets list
- `loadMore()` — appends next page
- `fetchUnclassifiedTransactions()` — populates swipe deck
- `classifyViaSwipe(transactionId:classification:essentialRatio:)` — submits classification, advances deck index, decrements `totalUnclassifiedCount`, calls `refresh()` when deck exhausted
- `classifyMerchant(merchantName:classification:essentialRatio:)` — merchant-level classification from transaction row tap
- `classifyTransaction(transactionId:subCategory:essentialRatio:)` — single transaction edit with local state patch (updates transaction in `transactions` array immediately)
- `autoClassifyWithAI()` — sets `isAutoClassifying = true`, calls `autoClassifyExpenses`, then `refresh()`
- `refresh()` — concurrent `async let` fetch of expenses (page 1) and unclassified transactions

Use `AuthManager.shared.authToken` (decoded JWT) to get `userId`.

---

## Phase 7: Frontend — ExpensesView

**File:** `BudgetBuddy/BudgetBuddy/Views/ExpensesView.swift`

### 7A. Main View — `ExpensesView`

```
NavigationStack
  ScrollView (vertical)
    VStack(spacing: 20)
      ExpensesSummaryCard          ← always visible
      SwipeClassificationCard       ← visible when totalUnclassifiedCount > 0
      "Auto-Classify" button        ← visible when totalUnclassifiedCount > 5
      Filter chips (HStack)         ← All / Essential / Fun Money / Split / Unclassified
      LazyVStack(transaction rows)
        ExpenseTransactionRow (per transaction)
      "Load More" button            ← visible when hasMore
```

`.task` modifier calls `vm.refresh()` on appear.
`.refreshable` on ScrollView calls `vm.refresh()`.

### 7B. `ExpensesSummaryCard`

A card showing a segmented horizontal bar divided into three colored segments:
- Essential: `Color.accent` (teal)
- Fun Money: `Color.danger` (coral)
- Unclassified: `Color(.systemGray4)`

Below the bar: a legend row for each segment showing a colored dot, label, and dollar amount.

Total spending shown as large rounded headline at top.

Uses `.cardStyle()` modifier.

### 7C. `SwipeClassificationCard`

Tinder-style swipe deck showing the current unclassified transaction:
- Merchant name (`.roundedHeadline`)
- Amount formatted as currency
- Date and category caption
- Swipe RIGHT → Essential (green overlay + "Essential" label)
- Swipe LEFT → Fun Money (coral overlay + "Fun Money" label)
- Swipe UP → Split (opens `SplitHalfSheet`)
- Drag threshold: 80pt before classification commits

Implementation:
```swift
@State private var dragOffset: CGSize = .zero
var dragGesture: some Gesture {
    DragGesture()
        .onChanged { value in dragOffset = value.translation }
        .onEnded { value in
            if value.translation.width > 80 { classifyEssential() }
            else if value.translation.width < -80 { classifyFunMoney() }
            else if value.translation.height < -80 { showSplit() }
            else { withAnimation { dragOffset = .zero } }
        }
}
```

Hint icons at the bottom: ← Fun Money, ↑ Split, → Essential

Counter badge: "X left to classify"

### 7D. `SplitHalfSheet`

`.sheet` presented over `SwipeClassificationCard` when user swipes up:
- Title: merchant name
- Slider (0–100%) with live update
- Two labels: "Essential: $X.XX" and "Fun Money: $Y.YY" (calculated from slider × amount)
- "Confirm Split" button

### 7E. `ExpenseTransactionRow`

List row showing:
- Left: merchant name (`.roundedBody`) + date (`.roundedCaption`, `.textSecondary`)
- Right: amount formatted as currency + `ClassificationBadge`

`ClassificationBadge` — small colored capsule:
- Essential → accent teal, "Essential"
- Fun Money → danger coral, "Fun Money"
- Split → purple, "Split X%/Y%"
- Unclassified → gray, "Unclassified"

Tapping a row sets `vm.selectedTransaction` and presents `TransactionClassificationSheet`.

### 7F. `TransactionClassificationSheet`

`.sheet` with:
- Segmented picker: Essential | Fun Money | Split
- Slider (only shown when "Split" selected)
- "Apply to All [Merchant]" toggle — if on, calls `classifyMerchant` instead of `classifyTransaction`
- "Save" button

### 7G. Filter Chips

Horizontal `ScrollView` with `HStack` of pill buttons:
- "All", "Essential", "Fun Money", "Split", "Unclassified"
- Selected chip uses `.accent` background, unselected uses `.surface`
- Tapping updates `vm.selectedFilter` and calls `vm.fetchExpenses()`

---

## Phase 8: Navigation Integration

**File:** `BudgetBuddy/BudgetBuddy/Views/ContentView.swift`

Add `ExpensesView` as a new tab in the `TabView`:
```swift
ExpensesView()
    .tabItem {
        Label("Expenses", systemImage: "list.bullet.rectangle")
    }
```

Place between the Plan tab and Chat tab (or as the second tab — confirm with design).

---

## Key Files Created/Modified

**Created:**
- `BudgetBuddyBackend/api/expenses.py` — all expense API endpoints
- `BudgetBuddyBackend/services/classification_service.py` — classification logic + LLM integration
- `BudgetBuddy/BudgetBuddy/ExpensesViewModel.swift` — view model
- `BudgetBuddy/BudgetBuddy/Views/ExpensesView.swift` — full UI

**Modified:**
- `BudgetBuddyBackend/db_models.py` — MerchantClassification + DeviceToken entities, Transaction field additions
- `BudgetBuddyBackend/main.py` — register `expenses_bp`
- `BudgetBuddy/BudgetBuddy/Models.swift` — expense model structs
- `BudgetBuddy/BudgetBuddy/APIService.swift` — 5 new API methods
- `BudgetBuddy/BudgetBuddy/Views/ContentView.swift` — Expenses tab entry

---

## Implementation Order

| Step | What | Dependencies |
|------|------|-------------|
| 1 | Backend: db_models.py — MerchantClassification + DeviceToken + Transaction fields | None |
| 2 | Backend: classification_service.py — pre-seeded defaults, priority chain, helpers | Step 1 |
| 3 | Backend: classification_service.py — LLM inference (single + batch) | Step 2 |
| 4 | Backend: api/expenses.py — all endpoints | Steps 1–3 |
| 5 | Backend: main.py — register blueprint | Step 4 |
| 6 | Frontend: Models.swift — add expense structs | None |
| 7 | Frontend: APIService.swift — add 5 methods | Step 6 |
| 8 | Frontend: ExpensesViewModel.swift | Step 7 |
| 9 | Frontend: ExpensesView.swift — summary card + transaction list | Step 8 |
| 10 | Frontend: ExpensesView.swift — swipe classification card + split sheet | Step 8 |
| 11 | Frontend: ExpensesView.swift — transaction row + classify sheet | Step 8 |
| 12 | Frontend: ContentView.swift — add Expenses tab | Steps 9–11 |

---

## Design Notes

- Use `Color.accent` (teal) for Essential, `Color.danger` (coral) for Fun Money consistently across all UI
- `.cardStyle()` modifier on all cards
- `.roundedHeadline`, `.roundedBody`, `.roundedCaption` fonts throughout
- Swipe card should feel snappy — use `withAnimation(.spring())` on drag release
- Empty state for transaction list: "No transactions found. Link your bank account via Plaid to get started."
- Empty state for swipe deck: "All caught up! Every transaction is classified." with a checkmark icon

---

## Verification

1. Run backend: `cd BudgetBuddyBackend && python main.py` — verify startup without errors
2. Test classification priority chain with known Plaid categories (rent → essential, netflix → fun_money)
3. Test `GET /expenses/<user_id>` — verify lazy backfill runs on first load
4. Test `POST /merchant/classify` — verify retroactive reclassification updates all matching transactions
5. Test `PUT /transaction/<id>/classify` — verify confidence threshold auto-promotion at count = 3
6. Test `POST /expenses/auto-classify/<user_id>` — verify LLM batch response is valid JSON
7. Build iOS app in Xcode — verify compilation with no errors
8. Test swipe flow: swipe right → transaction classified as Essential in list
9. Test swipe up → split sheet appears → slider → confirm → transaction shows split badge
10. Test auto-classify button: appears when > 5 unclassified, triggers spinner, list refreshes
11. Test filter chips: selecting "Essential" shows only essential transactions
12. Test "Load More": appends page 2 without duplicating page 1 results
13. Test merchant-level apply: classifying one transaction with "Apply to All [Merchant]" updates all others
