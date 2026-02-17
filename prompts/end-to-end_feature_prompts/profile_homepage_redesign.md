# BudgetBuddy: Profile Page, Homepage Redesign & Plaid Verification

## Context

BudgetBuddy has a working Plaid integration with a "Skip for now" button during onboarding, but no way for users to manage their bank connections afterward. The homepage (WalletView) shows generic financial cards but lacks actionable insights. This plan adds a **User Profile page** for managing settings and Plaid connections, **redesigns the homepage** with top expenses, goal progress, and AI nudges, and **verifies Plaid integration** correctness.

---

## Phase 1: Backend Changes

### 1A. Database Model Updates
**File:** `BudgetBuddyBackend/db_models.py`

- Add `name = db.Column(db.String(100), nullable=True)` to `User` model (after line 16)
- Add new `UserCategoryPreference` model:
  - `id`, `user_id` (FK), `category_name` (String), `display_order` (Int), `created_at`
- Add startup migration in `app.py` to ALTER TABLE for existing DBs (since `db.create_all()` won't add columns to existing tables in SQLite)

### 1B. New Backend Endpoints
**File:** `BudgetBuddyBackend/app.py`

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/user/profile/<user_id>` | GET | Fetch name, email, profile fields, linked Plaid accounts |
| `/user/profile/<user_id>` | PUT | Update name and/or any onboarding fields (partial update) |
| `/user/top-expenses/<user_id>?days=30` | GET | Aggregate top spending categories from Plaid transactions (fallback: statement) |
| `/user/category-preferences/<user_id>` | GET | Get user's pinned category preferences |
| `/user/category-preferences/<user_id>` | PUT | Set pinned categories `{ "categories": ["CAT1","CAT2","CAT3"] }` |
| `/user/nudges/<user_id>` | GET | Get rules-based smart nudges (actual vs. budget comparison) |

### 1C. Modified Existing Endpoints
- `POST /register` — optionally accept `name`
- `POST /login` — return `name` in response
- `POST /onboarding` — accept and save `name`

### 1D. New Service: Nudge Generator
**New file:** `BudgetBuddyBackend/services/nudge_generator.py`

Rules-based (no LLM dependency) nudge generation:
1. Fetch Plaid transactions (last 30 days), group by `category_primary`, sum amounts
2. Fetch latest `BudgetPlan`, extract `categoryAllocations`
3. Compare actual vs. planned for each category
4. Generate nudges: `spending_reduction` (over budget), `positive_reinforcement` (under budget), `goal_reminder` (goal progress)
5. Sort by impact, return top 3-5

Reuses existing logic patterns from `services/tools.py:_get_plaid_transactions()` (lines 114-216) and `_get_user_spending_status()` (lines 391-443).

---

## Phase 2: Frontend Model & Service Layer

### 2A. New Models
**File:** `BudgetBuddy/Models.swift`

Add after existing Plaid models (~line 415):
- `UserProfile` (name, email, profile: FinancialProfileInfo, plaidItems)
- `FinancialProfileInfo` (age, occupation, monthlyIncome, incomeFrequency, financialPersonality, primaryGoal)
- `UserProfileUpdateRequest` (all optional fields for partial update)
- `TopExpensesResponse` (source, topExpenses[], totalSpending, period)
- `TopExpense` (category, amount, transactionCount)
- `CategoryPreference` (id, categoryName, displayOrder)
- `SmartNudge` (type, title, message, potentialSavings?, category?)
- `PlaidItemInfo` (itemId, institutionName, status, accounts[])

### 2B. New API Methods
**File:** `BudgetBuddy/APIService.swift`

Add 6 methods following existing actor-based pattern:
- `getUserProfile(userId:)` → GET
- `updateUserProfile(userId:, update:)` → PUT
- `getTopExpenses(userId:, days:)` → GET
- `getCategoryPreferences(userId:)` → GET
- `updateCategoryPreferences(userId:, categories:)` → PUT
- `getNudges(userId:)` → GET

### 2C. AuthManager Updates
**File:** `BudgetBuddy/Services/AuthManager.swift`

- Add `userName: String?` property (persisted to UserDefaults)
- Update `login()` to store name from response
- Update `completeOnboarding()` to accept and send `name` parameter

---

## Phase 3: Onboarding — Name Collection

**File:** `BudgetBuddy/Views/Onboarding/OnboardingWizardView.swift`

- Add `@State private var name: String = ""`
- Insert new `NamePage` as page 0 (text field for name input)
- Shift existing pages (Age becomes page 1, etc.) — `totalPages` changes from 6 to 7
- Include `name` in the `finishOnboarding()` call
- Store name in `AuthManager.shared.userName`

---

## Phase 4: User Profile Page

### 4A. ProfileViewModel
**New file:** `BudgetBuddy/ProfileViewModel.swift`

`@Observable @MainActor` class with:
- Profile state (name, email, age, occupation, income, etc.)
- Plaid items list
- `loadProfile()` async — calls `getUserProfile`
- `saveProfile()` async — calls `updateUserProfile`
- `unlinkPlaidItem(itemId:)` async — calls existing `DELETE /plaid/unlink/`
- Edit mode toggle

### 4B. ProfileView
**New file:** `BudgetBuddy/Views/ProfileView.swift`

Layout (NavigationStack > ScrollView > VStack):
1. **Profile Header Card** — Avatar circle (initials), name (editable), email (read-only)
2. **Financial Profile Section** — Cards for each onboarding field with inline editing. Options match onboarding (occupation picker, income text field, frequency picker, personality picker, goal picker)
3. **Linked Accounts Section** — List of PlaidItem cards with institution name, account count, status. Each has "Unlink" button. "Link New Account" button at bottom triggers PlaidLink flow
4. **Sign Out Button** — Moved here from WalletView toolbar

### 4C. Navigation Integration
**File:** `BudgetBuddy/Views/ContentView.swift`

No changes needed — ProfileView is navigated to from WalletView toolbar.

**File:** `BudgetBuddy/Views/WalletView.swift` (toolbar only)

Replace sign-out button (lines 87-95) with `NavigationLink` to `ProfileView` using `person.circle` icon.

---

## Phase 5: Homepage (WalletView) Redesign

### 5A. WalletViewModel Updates
**File:** `BudgetBuddy/WalletViewModel.swift`

Add new state:
- `topExpenses: [TopExpense]`, `customCategories: [String]`, `expenseSource: String`
- `nudges: [SmartNudge]`
- `showCategoryEditor: Bool`

Add new methods:
- `fetchTopExpenses()` async
- `fetchNudges()` async
- `loadCategoryPreferences()` async
- `updateCategoryPreferences(_:)` async

Update `refresh()` to call all fetches concurrently via `async let`.

### 5B. New Card Components

**New file:** `BudgetBuddy/Views/Wallet/TopExpensesCard.swift`
- Shows top 3 expense categories with icon, name, amount, proportional bar
- Source badge ("via Plaid" / "via Statement")
- "Customize" button opens `CategoryEditorSheet`
- `CategoryEditorSheet`: list of available categories with checkboxes, save button
- Empty state: "Link your bank to see spending insights"

**New file:** `BudgetBuddy/Views/Wallet/GoalProgressSection.swift`
- Refactored from existing `GoalProgressCard` to show ALL goals (not just primary)
- Each goal: name, progress bar, current/target amounts
- Empty state: "Create a plan to set goals"

**New file:** `BudgetBuddy/Views/Wallet/SmartNudgesCard.swift`
- Shows 2-3 nudge rows
- Each nudge: colored icon (by type), title, message, savings badge (if applicable)
- Icon mapping: `spending_reduction` → `arrow.down.circle.fill` (danger), `positive_reinforcement` → `checkmark.circle.fill` (accent), `goal_reminder` → `target` (accent)
- Empty state: "Insights will appear as we learn your spending patterns"

### 5C. WalletView Body Redesign
**File:** `BudgetBuddy/Views/WalletView.swift`

New layout:
```
NavigationStack > ScrollView > VStack(spacing: 24)
  1. Header: "Hey, [Name]!" greeting + date subtitle  (or "Financial Overview" if no name)
  2. [KEPT] Net Worth + Safe to Spend cards (HStack, top row)
  3. [NEW] TopExpensesCard (from walletViewModel.topExpenses)
  4. [REFACTORED] GoalProgressSection (from planViewModel goals, showing all goals)
  5. [NEW] SmartNudgesCard (from walletViewModel.nudges)
  6. [KEPT] HintCard (if no plan)
```

**Removed cards:** `LinkedStatementCard`, `UploadStatementPromptCard`, `AnomaliesCard`, `UpcomingBillsCard`. Statement upload moves to Profile page or remains accessible via Chat.

---

## Phase 6: Plaid Integration Verification

Verify the existing flow end-to-end (no new code, just testing):
1. `.env` has `PLAID_CLIENT_ID`, `PLAID_SECRET`, `PLAID_ENV=sandbox`, `FERNET_KEY`
2. `POST /plaid/link-token` returns valid link token
3. iOS PlaidLink flow presents and completes in simulator
4. `POST /plaid/exchange-token` saves PlaidItem + accounts + transactions to DB
5. `GET /plaid/accounts/<user_id>` returns saved accounts
6. `GET /plaid/transactions/<user_id>` returns saved transactions
7. `DELETE /plaid/unlink/<user_id>/<item_id>` cleans up properly

Fix any issues found during verification.

---

## Implementation Order

| Step | What | Dependencies |
|------|------|-------------|
| 1 | Backend: db_models.py (User.name, UserCategoryPreference) + migration | None |
| 2 | Backend: New endpoints (profile, top-expenses, category-prefs) | Step 1 |
| 3 | Backend: nudge_generator.py + nudges endpoint | Step 1 |
| 4 | Backend: Modify register/login/onboarding for name | Step 1 |
| 5 | Plaid verification (test existing flow) | None (parallel with 1-4) |
| 6 | Frontend: Models.swift + APIService.swift additions | Steps 2-4 |
| 7 | Frontend: AuthManager.swift userName updates | Step 4 |
| 8 | Frontend: OnboardingWizardView name page | Step 7 |
| 9 | Frontend: ProfileViewModel + ProfileView | Steps 6-7 |
| 10 | Frontend: WalletViewModel updates | Step 6 |
| 11 | Frontend: TopExpensesCard, GoalProgressSection, SmartNudgesCard | Step 10 |
| 12 | Frontend: WalletView redesign + toolbar ProfileView link | Steps 9, 11 |

---

## Key Files Modified/Created

**Modified:**
- `BudgetBuddyBackend/db_models.py` — User.name + UserCategoryPreference
- `BudgetBuddyBackend/app.py` — 6 new + 3 modified endpoints + migration
- `BudgetBuddy/Models.swift` — 8 new model structs
- `BudgetBuddy/APIService.swift` — 6 new API methods
- `BudgetBuddy/Services/AuthManager.swift` — userName property
- `BudgetBuddy/Views/Onboarding/OnboardingWizardView.swift` — name page
- `BudgetBuddy/Views/WalletView.swift` — redesigned body + toolbar
- `BudgetBuddy/WalletViewModel.swift` — new state + fetch methods

**Created:**
- `BudgetBuddyBackend/services/nudge_generator.py`
- `BudgetBuddy/ProfileViewModel.swift`
- `BudgetBuddy/Views/ProfileView.swift`
- `BudgetBuddy/Views/Wallet/TopExpensesCard.swift`
- `BudgetBuddy/Views/Wallet/GoalProgressSection.swift`
- `BudgetBuddy/Views/Wallet/SmartNudgesCard.swift`

## Verification

1. Run backend: `cd BudgetBuddyBackend && python app.py` — verify startup with migration
2. Test new endpoints with curl (profile GET/PUT, top-expenses, nudges)
3. Build iOS app in Xcode — verify compilation
4. Test flow: Register → Onboarding (name page) → Plaid Link → Homepage shows data
5. Test profile page: edit fields, unlink/link Plaid, sign out
6. Test homepage: top expenses load, category customization works, nudges appear, goals display
7. Test empty states: new user with no Plaid data and no plan
