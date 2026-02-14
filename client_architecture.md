# Client Architecture (iOS - SwiftUI)

## High-Level Overview
The iOS client uses a modern **MVVM (Model-View-ViewModel)** architecture with **SwiftUI**. The core differentiator is the "Generative UI" engine, which renders native SwiftUI views based on JSON payloads received from the LLM.

---

## Key Modules

### 1. ChatViewModel (ViewModel)
* **Responsibility:** Manages the conversation state using `@Observable` macro. Sends user input to the backend and handles response parsing.
* **Key Logic:** Toggle `useRealAPI` to switch between real backend and mock data. Distinguishes between text-only responses and those carrying a `visualPayload`.

### 2. GenerativeWidgetView (View Factory)
* **Responsibility:** The "Generative UI" engine. Takes a `VisualComponent` enum and returns the corresponding SwiftUI View.
* **Capabilities:** Can render `BurndownWidgetView`, `BudgetSliderView`, or `SankeyFlowView` on demand based on the variant received from the backend.

### 3. APIService (Network Layer)
* **Responsibility:** Actor-isolated (`actor`) service for thread-safe async communication with the Flask backend. All network calls are `async throws` and return strongly-typed response models.
* **Base URL:** Configurable at init; the shared singleton defaults to `http://127.0.0.1:5000` (iOS Simulator).

#### Methods

| Method | HTTP | Endpoint | Notes |
|---|---|---|---|
| `sendMessage(text:userId:)` | `POST` | `/chat` | Core chat loop. Sends `{ message, userId }`, returns `AssistantResponse`. |
| `uploadStatement(fileURL:)` | `POST` | `/upload-statement` | Reads a local PDF/CSV, builds a `multipart/form-data` body with a UUID boundary, returns `AssistantResponse`. |
| `healthCheck()` | `GET` | `/health` | Returns `Bool`. Swallows all errors internally — safe to call on launch. |
| `generatePlan(userId:planInput:)` | `POST` | `/generate-plan` | Serializes a `SpendingPlanInput` into the nested `deepDiveData` JSON shape the backend expects. Returns `SpendingPlanResponse`. |
| `getPlan(userId:)` | `GET` | `/get-plan/<userId>` | Fetches the most recent persisted plan. Returns `GetPlanResponse`. |
| `getFinancialSummary(userId:)` | `GET` | `/user/financial-summary` | Gets net worth, safe-to-spend, and statement info. Returns `FinancialSummary`. |
| `getUserProfile(userId:)` | `GET` | `/user/profile/<id>` | Fetches name, email, financial profile, and linked Plaid accounts. Returns `UserProfile`. |
| `updateUserProfile(userId:update:)` | `PUT` | `/user/profile/<id>` | Partial update of profile fields. Accepts `UserProfileUpdateRequest`. |
| `getTopExpenses(userId:days:)` | `GET` | `/user/top-expenses/<id>` | Aggregates top spending categories. Returns `TopExpensesResponse`. |
| `getCategoryPreferences(userId:)` | `GET` | `/user/category-preferences/<id>` | Gets pinned category preferences. Returns `CategoryPreferencesResponse`. |
| `updateCategoryPreferences(userId:categories:)` | `PUT` | `/user/category-preferences/<id>` | Sets pinned categories. |
| `getNudges(userId:)` | `GET` | `/user/nudges/<id>` | Gets smart nudges comparing actual vs. budget spending. Returns `NudgesResponse`. |

### 4. MockService (Offline Development)
* **Responsibility:** Provides simulated responses that mirror the real `APIService` signatures, allowing UI development and testing without a running backend.

### 5. AuthManager (Singleton)
* **Responsibility:** Manages authentication state (login, register, onboarding), persists `authToken` and `userName` to `UserDefaults`.
* **Key Logic:** `@Observable` class for reactive UI updates. Handles login, register, completeOnboarding (with name support), and signOut.

### 6. PlaidLinkManager / PlaidService
* **Responsibility:** Wraps the Plaid Link SDK for iOS. Manages the bank account linking flow — creating link tokens, presenting the Plaid Link UI, and exchanging public tokens.

### 7. ProfileViewModel
* **Responsibility:** `@Observable @MainActor` view model for the user profile page. Loads/saves profile data, manages Plaid item unlinking.

### 8. WalletViewModel
* **Responsibility:** Manages wallet dashboard state including financial summary, top expenses, smart nudges, and category preferences. Fetches all data concurrently on refresh.

---

## Key Data Structures

### Response Types

```swift
// The hybrid response object from the AI (chat + statement upload)
struct AssistantResponse: Codable {
    let textMessage: String
    let visualPayload: VisualComponent? // Only present when the backend wants to show a widget
}

// Returned by POST /generate-plan
struct SpendingPlanResponse: Codable {
    let textMessage: String
    let plan: [String: Any]          // The full generated budget plan
    let visualPayload: [String: Any]? // Optional chart/widget data
}

// Returned by GET /get-plan/<userId>
struct GetPlanResponse: Codable {
    let hasPlan: Bool
    let plan: [String: Any]?
    let createdAt: String?           // ISO 8601 timestamp
    let monthYear: String?           // e.g. "2026-02"
}
```

### The Generative UI Enum

```swift
enum VisualComponent: Codable {
    case budgetBurndown(data: [BurndownDataPoint])
    case sankeyFlow(nodes: [SankeyNode])
    case interactiveSlider(category: String, current: Double, max: Double)
    case burndownChart(spent: Double, budget: Double, idealPace: Double)
    case budgetSlider(category: String, current: Double, max: Double)
}
```

### Input Types

```swift
// Top-level input to generatePlan — mirrors the deepDiveData payload
struct SpendingPlanInput {
    let fixedExpenses:      FixedExpenses
    let variableSpending:   VariableSpending
    let upcomingEvents:     [UpcomingEvent]
    let savingsGoals:       [SavingsGoal]
    let spendingPreferences: SpendingPreferences
}

// --- Fixed Expenses ---
struct FixedExpenses {
    let rent:          Double
    let utilities:     Double
    let subscriptions: [Subscription]   // name + amount
}

// --- Variable Spending ---
struct VariableSpending {
    let groceries:          Double
    let transportation:     Transportation
    let diningEntertainment: Double
}

struct Transportation {
    let type:       String  // e.g. "car", "public"
    let gas:        Double
    let insurance:  Double
    let transitPass: Double
}

// --- Upcoming Events ---
struct UpcomingEvent {
    let name:         String
    let date:         Date       // serialized as ISO 8601 by generatePlan
    let cost:         Double
    let saveGradually: Bool
}

// --- Savings Goals ---
struct SavingsGoal {
    let name:     String
    let target:   Double
    let current:  Double
    let priority: Int
}

// --- Spending Preferences ---
struct SpendingPreferences {
    let spendingStyle: Double   // 0.0 – 1.0 slider value
    let priorities:    [String] // e.g. ["savings", "security"]
    let strictness:    String   // e.g. "moderate", "strict", "flexible"
}
```

### Profile & Dashboard Types

```swift
// User profile with financial info and linked accounts
struct UserProfile: Codable {
    let name: String?
    let email: String
    let profile: FinancialProfileInfo?
    let plaidItems: [PlaidItemInfo]
}

// Partial update request (all fields optional)
struct UserProfileUpdateRequest: Codable {
    var name: String?
    var age: Int?
    var occupation: String?
    var monthlyIncome: Double?
    var incomeFrequency: String?
    var financialPersonality: String?
    var primaryGoal: String?
}

// Top spending categories
struct TopExpensesResponse: Codable {
    let source: String       // "plaid", "statement", or "none"
    let topExpenses: [TopExpense]
    let totalSpending: Double
    let period: Int
}

// Smart nudges (rules-based, no LLM)
struct SmartNudge: Codable, Identifiable {
    let type: String?            // "spending_reduction", "positive_reinforcement", "goal_reminder"
    let title: String?
    let message: String?
    let potentialSavings: Double?
    let category: String?
}
```

### Errors

```swift
enum APIError: LocalizedError {
    case invalidResponse                // Response couldn't be cast to HTTPURLResponse
    case serverError(statusCode: Int)   // Non-200 status from the backend
    case decodingError(Error)           // JSONDecoder failed on the response body
}
```

### Legacy / Unused (kept for reference)

```swift
struct Transaction: Identifiable, Codable {
    let id: UUID
    let amount: Decimal
    let merchant: String
    let category: BudgetCategory
    let date: Date
}
```
