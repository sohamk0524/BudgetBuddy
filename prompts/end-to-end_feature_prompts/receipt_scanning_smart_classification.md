# BudgetBuddy: Receipt Scanning + Smart Auto-Classification

## Context

Two features to make expense classification near-zero-effort:
1. **Receipt Scanning** — user photos a receipt (camera, library, or iOS Share Extension), Claude Vision extracts line items, classifies each as essential/discretionary, and either enriches an existing Plaid transaction or creates a new manual transaction. When a matching Plaid transaction arrives later, it backfills metadata into the receipt-created transaction.
2. **Smart Classification** — expand pre-seeded defaults to silently auto-classify all common discretionary/mixed Plaid categories (coffee, restaurants, entertainment, groceries-as-mixed) so they never appear in the swipe deck. Add a frontend challenge alert when a user tries to mark an obviously-discretionary transaction as essential.

---

## Feature 1: Receipt Scanning

### 1A. Backend — Receipt Vision Service

**New file:** `BudgetBuddyBackend/services/receipt_service.py`

Uses the Anthropic Python SDK directly (not `llm_service.Agent`, which is text-only) with Claude's vision API:

```python
import anthropic, base64, json

def analyze_receipt(image_data: bytes, media_type: str) -> dict:
    client = anthropic.Anthropic()
    prompt = """Analyze this receipt image. Extract:
1. Merchant name and total amount
2. Every line item with its price
3. Classify each item: "essential" (food staples, household necessities, medicine)
   or "discretionary" (snacks, alcohol, cosmetics, entertainment, clothing, luxury)

Respond ONLY with valid JSON:
{
  "merchant": "string",
  "total": float,
  "items": [{"name": "string", "price": float, "classification": "essential"|"discretionary"}],
  "essentialTotal": float,
  "discretionaryTotal": float
}"""
    msg = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=2048,
        messages=[{"role": "user", "content": [
            {"type": "image", "source": {
                "type": "base64",
                "media_type": media_type,
                "data": base64.standard_b64encode(image_data).decode()
            }},
            {"type": "text", "text": prompt}
        ]}]
    )
    return json.loads(msg.content[0].text)
```

### 1B. Backend — Receipt API Endpoints

**New file:** `BudgetBuddyBackend/api/receipt.py` — blueprint `receipt_bp`

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/receipt/analyze` | Accept image upload, call Claude Vision, return line items |
| POST | `/receipt/attach` | Find matching Plaid transaction or create ManualTransaction |

**`POST /receipt/analyze`**
- Accepts `multipart/form-data`: `file` (JPEG/PNG/HEIC), `userId` (int)
- Calls `receipt_service.analyze_receipt()`
- Returns `ReceiptAnalysisResult` JSON

**`POST /receipt/attach`**
Body: `{ userId, merchant, total, items, essentialTotal, discretionaryTotal, date }`

Logic:
1. Look for an existing Plaid `Transaction` within ±2 days and amount within ±$2 of `total`, merchant name similarity ≥ 0.7 (`difflib.SequenceMatcher`)
2. **If match found**: enrich it — set `sub_category`, `essential_amount`, `discretionary_amount`, `receipt_items` (JSON string), `receipt_image_url`
3. **If no match**: create a new `ManualTransaction` with all receipt data + `sub_category` + ratio + `receipt_items` JSON + `pending_plaid_reconcile=True`
4. Returns: `{ transactionId, source: "plaid"|"manual", enriched: bool }`

**`db_models.py` additions:**
- `find_matching_transaction(user_id, amount, date_str, merchant)` — queries Transactions by account_ids within ±2 days, filters by amount/merchant in Python
- `reconcile_manual_with_plaid(manual_id, plaid_txn_data)` — copies Plaid metadata (`transaction_id`, `merchant_name`, `category_primary`, `category_detailed`, `payment_channel`) into a ManualTransaction, sets `pending_plaid_reconcile=False`
- New fields on both entity kinds: `receipt_items` (JSON string), `receipt_image_url` (str), `pending_plaid_reconcile` (bool, ManualTransaction only)

### 1C. Backend — Plaid Reconciliation

**`BudgetBuddyBackend/api/plaid.py`** — in the transaction sync loop, after `create_transaction(...)`:

```python
# Check for pending receipt-created ManualTransaction to reconcile
pending = find_pending_receipt_transaction(
    user_id, txn_data["amount"], txn_data["date"], txn_data["merchant_name"]
)
if pending:
    reconcile_manual_with_plaid(pending.key.id, txn_data)
    # Don't create duplicate — ManualTransaction is the source of truth
    continue
```

`find_pending_receipt_transaction` checks `ManualTransaction` entities with `pending_plaid_reconcile=True` for the user.

### 1D. Register Blueprint

**`BudgetBuddyBackend/main.py`**: `from api.receipt import receipt_bp` + `app.register_blueprint(receipt_bp)`

---

### 1E. iOS — Models

**`BudgetBuddy/Models.swift`** — add after existing expense models:

```swift
struct ReceiptLineItem: Codable, Identifiable {
    let id = UUID()
    let name: String
    let price: Double
    let classification: String  // "essential" | "discretionary"
    var isEssential: Bool { classification == "essential" }
    enum CodingKeys: String, CodingKey { case name, price, classification }
}

struct ReceiptAnalysisResult: Codable {
    let merchant: String
    let total: Double
    let items: [ReceiptLineItem]
    let essentialTotal: Double
    let discretionaryTotal: Double
}

struct ReceiptAttachRequest: Codable {
    let userId: Int
    let merchant: String
    let total: Double
    let items: [ReceiptLineItem]
    let essentialTotal: Double
    let discretionaryTotal: Double
    let date: String
}

struct ReceiptAttachResponse: Codable {
    let transactionId: Int
    let source: String   // "plaid" | "manual"
    let enriched: Bool
}
```

### 1F. iOS — APIService

**`BudgetBuddy/APIService.swift`** — add two methods following existing actor pattern:

```swift
func analyzeReceipt(imageData: Data, userId: Int) async throws -> ReceiptAnalysisResult
// POST /receipt/analyze — multipart/form-data with "file" + "userId"

func attachReceipt(request: ReceiptAttachRequest) async throws -> ReceiptAttachResponse
// POST /receipt/attach — JSON body
```

### 1G. iOS — ReceiptScanViewModel

**New file:** `BudgetBuddy/ReceiptScanViewModel.swift`

```swift
@Observable @MainActor
class ReceiptScanViewModel {
    enum State { case idle, analyzing, reviewed, attaching, done, error(String) }
    var state: State = .idle
    var capturedImage: UIImage?
    var analysisResult: ReceiptAnalysisResult?
    var attachResponse: ReceiptAttachResponse?

    func analyzeImage(_ image: UIImage) async { ... }
    func confirmAndAttach(date: String) async { ... }
    func reset() { state = .idle; capturedImage = nil; analysisResult = nil }
}
```

### 1H. iOS — ReceiptScanView + ReceiptLineItemsView

**New file:** `BudgetBuddy/Views/Receipt/ReceiptScanView.swift`

Sheet triggered from `ExpensesView` via a "Scan Receipt" button (alongside the existing voice log button):

```
Sheet: ReceiptScanView
  ├─ State = idle:
  │    Three options: [Camera] [Photo Library] [Cancel]
  │    Camera → UIImagePickerController(sourceType: .camera)
  │    Library → PhotosPicker (SwiftUI)
  │
  ├─ State = analyzing:
  │    ProgressView + "Reading your receipt..."
  │
  └─ State = reviewed:
       ReceiptLineItemsView(result: analysisResult)
         → on confirm → vm.confirmAndAttach() → dismiss + refresh
```

**New file:** `BudgetBuddy/Views/Receipt/ReceiptLineItemsView.swift`

```
VStack
  ┌─ Summary card (cardStyle) ──────────────────┐
  │  Merchant name (.roundedLargeTitle)          │
  │  Total: $XX.XX (.roundedHeadline)            │
  │  Segmented bar: teal essential / coral disc  │
  │  Essential: $X   Discretionary: $X          │
  └──────────────────────────────────────────────┘

  ScrollView → LazyVStack
    ForEach items:
      HStack
        RoundedRectangle(4pt wide)
          .fill(item.isEssential ? Color.accent : Color.danger)
        Text(item.name)   Spacer   Text("$\(item.price, format:.currency)")

  Button "Confirm & Save" (accent background, full width)
    → vm.confirmAndAttach()
```

No text labels for essential/discretionary — teal/coral color bars only, per user preference.

### 1I. iOS — Share Extension

**New Xcode Target:** `BudgetBuddyShareExtension` (Share Extension type)

- `Info.plist`: `NSExtensionActivationRule` accepts `public.image`
- App Group: `group.sample.BudgetBuddy` (add to both main app and extension entitlements)

**Flow:**
1. User opens Photos → selects receipt → Share → BudgetBuddy
2. Extension saves image to App Group: `FileManager.containerURL(forSecurityApplicationGroupIdentifier:)` as `receipt_pending.jpg`
3. Extension opens main app via URL scheme `budgetbuddy://receipt`
4. Main app `BudgetBuddyApp.swift`: `.onOpenURL` handler detects `budgetbuddy://receipt` → reads image from shared container → presents `ReceiptScanView` pre-loaded in `.analyzing` state

---

## Feature 2: Smart Classification

### 2A. Backend — Expanded Pre-seeded Defaults

**`BudgetBuddyBackend/services/classification_service.py`**

Add after existing `PRIMARY_CATEGORY_DEFAULTS`:

```python
DISCRETIONARY_DEFAULTS = {
    # Entertainment — all discretionary
    "ENTERTAINMENT_CASINOS_AND_GAMBLING": ("discretionary", 0.0),
    "ENTERTAINMENT_CONCERTS_AND_EVENTS": ("discretionary", 0.0),
    "ENTERTAINMENT_MOVIES_AND_MUSIC": ("discretionary", 0.0),
    "ENTERTAINMENT_SPORTING_EVENTS": ("discretionary", 0.0),
    "ENTERTAINMENT_TV_AND_MOVIES": ("discretionary", 0.0),
    "ENTERTAINMENT_VIDEO_GAMES": ("discretionary", 0.0),
    "ENTERTAINMENT_OTHER_ENTERTAINMENT": ("discretionary", 0.0),
    # Food & Drink
    "FOOD_AND_DRINK_BEER_WINE_AND_LIQUOR": ("discretionary", 0.0),
    "FOOD_AND_DRINK_COFFEE": ("discretionary", 0.0),
    "FOOD_AND_DRINK_FAST_FOOD": ("discretionary", 0.0),
    "FOOD_AND_DRINK_RESTAURANTS": ("discretionary", 0.0),
    "FOOD_AND_DRINK_VENDING_MACHINES": ("discretionary", 0.0),
    "FOOD_AND_DRINK_GROCERIES": ("mixed", 0.8),  # 80% essential by default
    # Personal Care
    "PERSONAL_CARE_HAIR_AND_BEAUTY": ("discretionary", 0.0),
    "PERSONAL_CARE_GYMS_AND_FITNESS_CENTERS": ("discretionary", 0.0),
    "PERSONAL_CARE_LAUNDRY_AND_DRY_CLEANING": ("essential", 1.0),
    # Transportation
    "TRANSPORTATION_GAS": ("essential", 1.0),
    "TRANSPORTATION_PARKING": ("mixed", 0.5),
    "TRANSPORTATION_PUBLIC_TRANSIT": ("essential", 1.0),
    "TRANSPORTATION_TAXIS_AND_RIDE_SHARING": ("mixed", 0.5),
    # Travel
    "TRAVEL_FLIGHTS": ("discretionary", 0.0),
    "TRAVEL_LODGING": ("discretionary", 0.0),
    "TRAVEL_RENTAL_CARS": ("discretionary", 0.0),
    # General Merchandise (mixed)
    "GENERAL_MERCHANDISE_DISCOUNT_STORES": ("mixed", 0.5),
    "GENERAL_MERCHANDISE_ONLINE_MARKETPLACES": ("mixed", 0.4),
    "GENERAL_MERCHANDISE_SUPERSTORES": ("mixed", 0.6),
    # Government
    "GOVERNMENT_AND_NON_PROFIT_TAX_PAYMENT": ("essential", 1.0),
}

PRIMARY_DISCRETIONARY_DEFAULTS = {
    "ENTERTAINMENT": ("discretionary", 0.0),
    "FOOD_AND_DRINK": ("mixed", 0.6),
    "PERSONAL_CARE": ("discretionary", 0.0),
    "TRAVEL": ("discretionary", 0.0),
    "GENERAL_MERCHANDISE": ("mixed", 0.5),
    "TRANSPORTATION": ("mixed", 0.7),
}

# Subset used for the frontend challenge prompt
OBVIOUSLY_DISCRETIONARY_CATEGORIES = {
    "FOOD_AND_DRINK_COFFEE", "FOOD_AND_DRINK_BEER_WINE_AND_LIQUOR",
    "ENTERTAINMENT_MOVIES_AND_MUSIC", "ENTERTAINMENT_CONCERTS_AND_EVENTS",
    "ENTERTAINMENT_TV_AND_MOVIES", "ENTERTAINMENT_VIDEO_GAMES",
    "ENTERTAINMENT_CASINOS_AND_GAMBLING", "FOOD_AND_DRINK_FAST_FOOD",
    "ENTERTAINMENT_SPORTING_EVENTS",
}
```

Update `classify_transaction()` priority chain — insert new steps 2b and 3b:

```
1. User MerchantClassification (override, always respected)
2. PRE_SEEDED_DEFAULTS[detailed]        ← essential by Plaid detailed category
2b. DISCRETIONARY_DEFAULTS[detailed]   ← NEW: discretionary/mixed by detailed
3. PRIMARY_CATEGORY_DEFAULTS[primary]  ← essential by Plaid primary
3b. PRIMARY_DISCRETIONARY_DEFAULTS[primary]  ← NEW: discretionary/mixed by primary
4. LLM inference (use_llm=True only)
5. Leave as unclassified → appears in swipe deck
```

### 2B. Backend — Challenge Response Field

**`BudgetBuddyBackend/api/expenses.py`** — in `classify_single_transaction`:

After saving the classification, if `sub_category == 'essential'` and `txn.get('category_detailed')` is in `OBVIOUSLY_DISCRETIONARY_CATEGORIES`, include a `challenge` field in the response:

```python
from services.classification_service import OBVIOUSLY_DISCRETIONARY_CATEGORIES

challenge = None
if sub_category == 'essential':
    cat = txn.get('category_detailed', '')
    if cat in OBVIOUSLY_DISCRETIONARY_CATEGORIES:
        readable = cat.replace('_', ' ').title()
        challenge = {
            "show": True,
            "reason": f"{readable} is almost always discretionary spending. Are you sure this is essential?"
        }

return jsonify({
    "success": True,
    "transaction": { ... },
    "challenge": challenge,
    ...
})
```

### 2C. iOS — Models Update

**`BudgetBuddy/Models.swift`** — add `ChallengeInfo` and update `ClassifyTransactionResponse`:

```swift
struct ChallengeInfo: Codable {
    let show: Bool
    let reason: String?
}

// Update existing struct:
struct ClassifyTransactionResponse: Codable {
    let success: Bool
    let transaction: ClassifiedTransaction
    let updatedMerchantRatio: Double?
    let autoApplied: Int?
    let challenge: ChallengeInfo?   // NEW
}
```

### 2D. iOS — Challenge Alert in Classification Sheet

**`BudgetBuddy/Views/ExpensesView.swift`** — in `TransactionClassificationSheet`:

Add `@State private var pendingChallenge: ChallengeInfo?`

After `vm.classifyTransaction(...)` returns:
```swift
if let challenge = response.challenge, challenge.show == true {
    pendingChallenge = challenge
}
```

Add `.alert` modifier:
```swift
.alert("Are you sure?", isPresented: .constant(pendingChallenge != nil), presenting: pendingChallenge) { info in
    Button("Yes, it's Essential", role: .none) { pendingChallenge = nil }
    Button("Change to Discretionary") {
        Task { await vm.classifyTransaction(transactionId: ..., subCategory: "discretionary") }
        pendingChallenge = nil
    }
} message: { info in
    Text(info.reason ?? "This looks like discretionary spending.")
}
```

---

## Implementation Order

| Step | What | Files |
|------|------|-------|
| 1 | Expanded discretionary defaults + `OBVIOUSLY_DISCRETIONARY` set | `classification_service.py` |
| 2 | Challenge field in classify endpoint | `api/expenses.py` |
| 3 | `ChallengeInfo` model + updated `ClassifyTransactionResponse` | `Models.swift` |
| 4 | Challenge alert in classification sheet | `ExpensesView.swift` |
| 5 | `receipt_service.py` — Claude Vision analysis function | new file |
| 6 | `db_models.py` additions — match, reconcile helpers | `db_models.py` |
| 7 | `api/receipt.py` blueprint + register in `main.py` | new file + `main.py` |
| 8 | Plaid sync reconciliation hook | `api/plaid.py` |
| 9 | iOS models — ReceiptLineItem, ReceiptAnalysisResult, etc. | `Models.swift` |
| 10 | `analyzeReceipt` + `attachReceipt` in APIService | `APIService.swift` |
| 11 | `ReceiptScanViewModel` | new file |
| 12 | `ReceiptScanView` + `ReceiptLineItemsView` | new files |
| 13 | "Scan Receipt" button in `ExpensesView` | `ExpensesView.swift` |
| 14 | Share Extension target + App Group entitlement | new Xcode target |
| 15 | URL scheme handler in `BudgetBuddyApp.swift` | `BudgetBuddyApp.swift` |

Steps 1–4 (smart classification) are independent and fast.
Steps 5–13 (receipt core) are the main body.
Steps 14–15 (Share Extension) are additive, can be done last.

---

## Key Files

**Modified:**
- `BudgetBuddyBackend/services/classification_service.py`
- `BudgetBuddyBackend/api/expenses.py`
- `BudgetBuddyBackend/api/plaid.py`
- `BudgetBuddyBackend/db_models.py`
- `BudgetBuddyBackend/main.py`
- `BudgetBuddy/Models.swift`
- `BudgetBuddy/APIService.swift`
- `BudgetBuddy/Views/ExpensesView.swift`
- `BudgetBuddy/BudgetBuddy.entitlements`
- `BudgetBuddy/BudgetBuddyApp.swift`

**Created:**
- `BudgetBuddyBackend/services/receipt_service.py`
- `BudgetBuddyBackend/api/receipt.py`
- `BudgetBuddy/ReceiptScanViewModel.swift`
- `BudgetBuddy/Views/Receipt/ReceiptScanView.swift`
- `BudgetBuddy/Views/Receipt/ReceiptLineItemsView.swift`
- `BudgetBuddyShareExtension/` (new Xcode target — separate from main app)

---

## Verification

1. **Expanded defaults**: Add Plaid sandbox transaction with `category_detailed = "FOOD_AND_DRINK_COFFEE"` → verify it auto-classifies as `discretionary` without appearing in swipe deck
2. **Groceries as mixed**: Plaid grocery transaction → verify classified as `mixed` with `essential_ratio=0.8`
3. **Challenge prompt**: Tap a coffee transaction → classify as Essential → verify challenge alert appears with correct message → "Change to Discretionary" re-classifies it
4. **Challenge override**: Same flow → "Yes, it's Essential" → verify classification saved as essential without re-prompting
5. **Receipt analyze**: `POST /receipt/analyze` with sample receipt image → verify JSON has `items[]` with correct essential/discretionary per item
6. **Receipt attach (new)**: Receipt for merchant not in Plaid → verify `ManualTransaction` created with `receipt_items`, correct `essential_amount`/`discretionary_amount`, `pending_plaid_reconcile=True`
7. **Receipt attach (enrich)**: Receipt matching existing Plaid transaction → verify existing Transaction enriched, no duplicate
8. **Plaid reconciliation**: Create receipt-based ManualTransaction → sync Plaid with matching transaction → verify `plaid_transaction_id` set on ManualTransaction, no duplicate Transaction
9. **iOS receipt flow**: Tap "Scan Receipt" → Camera → capture → analyzing spinner → line items with teal/coral bars → Confirm → expenses list refreshes with new transaction
10. **Share Extension**: Share receipt from Photos → BudgetBuddy opens → receipt scan flow appears pre-loaded
