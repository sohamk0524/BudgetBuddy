# Instructions for Gemini CLI: BudgetBuddy UI Implementation

**Context:**
We are building the "BudgetBuddy" iOS app. The project skeleton already exists in `./BudgetBuddy/`.
You are an expert iOS Engineer specializing in **Polished SwiftUI Interfaces**.

**The Goal:**
Implement the "High-Fidelity" UI for the app based on a specific visual design language. The app consists of two main tabs:
1.  **The Command Center (Chat):** A hybrid interface with a "Pulse Header" and "Generative Widgets" inside the chat stream.
2.  **The Wallet (Dashboard):** A "Bento Box" style grid for quick status checks.

**Design System (Strict Adherence Required):**
* **Background:** Deep Midnight Blue (`#0F172A`).
* **Cards/Surfaces:** Lighter Slate Blue (`#1E293B`).
* **Accent Color:** Electric Teal (`#2DD4BF`) for positive/actions.
* **Danger Color:** Soft Coral (`#F43F5E`) for alerts (avoid harsh pure red).
* **Typography:** Use `.design(.rounded)` for all fonts. Numbers should be `.monospacedDigit()` where appropriate.

---

## Required File Generation

Please generate/overwrite the following Swift files with the code provided below. Ensure all files are placed correctly in the project structure.

### 1. `./BudgetBuddy/Design/Theme.swift`
* Create a `Color` extension to centralize our palette.
* Define: `background`, `surface`, `accent`, `danger`, `textPrimary`, `textSecondary`.
* Include a modifier `cardStyle()` that applies the standard padding, background, and rounded corners (cornerRadius: 16).

### 2. `./BudgetBuddy/Models/Models.swift`
* **Update** the existing file.
* Update `VisualComponent` enum to support:
    * `.burndownChart(spent: Double, budget: Double, idealPace: Double)`
    * `.budgetSlider(category: String, current: Double, max: Double)`
* Ensure `AssistantResponse` includes an optional `VisualComponent`.

### 3. `./BudgetBuddy/Services/MockService.swift`
* **Update** the mock data to show off the UI.
* The `sendMessage` function should return a response that simulates a "High Spending" alert, attaching a `.burndownChart` visual component to the message.

### 4. `./BudgetBuddy/Views/Components/PulseHeaderView.swift`
* **New View.** The "Sticky Header" for the chat.
* **Visuals:**
    * Display "Safe-to-Spend" in large rounded font (e.g., "$124").
    * Green/Teal background pill shape if healthy.
    * Show a small "Status: On Track" label below.

### 5. `./BudgetBuddy/Views/Components/BurndownWidgetView.swift`
* **New View.**
* Use SwiftCharts (import `Charts`) to render a Line Chart.
* **Data:** Plot a "Budget Limit" line and an "Actual Spending" line.
* **Style:** Minimalist. No grid lines. Use gradients for the area under the curve if possible.

### 6. `./BudgetBuddy/Views/Components/GenerativeWidgetView.swift`
* **New View.** A wrapper view.
* **Logic:** Switch on `VisualComponent`.
    * If `.burndownChart` -> return `BurndownWidgetView`.
    * If `.budgetSlider` -> return a simple `Slider` view (placeholder is fine).
* **Styling:** Wrap the result in the `cardStyle()` from Theme.

### 7. `./BudgetBuddy/Views/ChatView.swift`
* **Update** the main view.
* **Layout:** `ZStack` or `VStack`.
    * Top: `PulseHeaderView` (Pinned).
    * Middle: `ScrollView` for messages.
    * Bottom: Input Bar (Styled with a dark blur material background).
* **Message Row Logic:**
    * If `message.isUser`: Align right, gray bubble.
    * If `!message.isUser`: Align left, transparent background (text only).
    * **CRITICAL:** Immediately after the AI text, check `if let widget = message.visualPayload`. If it exists, render `GenerativeWidgetView(component: widget)`.

### 8. `./BudgetBuddy/Views/WalletView.swift`
* **New View.**
* **Layout:** A "Bento Box" Grid (use `LazyVGrid` or `HStack` of `VStacks`).
* **Components:**
    * **Large Card:** "Net Worth" (Top Left).
    * **Medium Card:** "Upcoming Bills" (Top Right).
    * **Small Cards:** "Anomalies" and "Goal Progress" (Bottom).
* **Style:** All cards must use the `surface` color and `cardStyle`.

### 9. `./BudgetBuddy/Views/ContentView.swift`
* **Update** root view.
* Implement a `TabView`.
    * Tab 1: `ChatView` (Icon: "message.fill").
    * Tab 2: `WalletView` (Icon: "wallet.pass.fill").
* Apply the `Theme.background` to the entire TabView to ensure no white edges appear.

---

**Output Format:**
Provide the full Swift code for every file listed above. Ensure imports (like `SwiftUI`, `Charts`) are correct.