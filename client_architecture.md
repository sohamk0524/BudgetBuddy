# Client Architecture (iOS - SwiftUI)

## High-Level Overview
The iOS client uses a modern **MVVM (Model-View-ViewModel)** architecture with **SwiftUI**. The core differentiator is the "Generative UI" engine, which renders native SwiftUI views based on JSON payloads received from the LLM.

## Key Modules

### 1. ChatViewModel (ViewModel)
* **Responsibility:** Manages the conversation state using `@Observable` macro. Sends user input to the backend and handles response parsing.
* **Key Logic:** Toggle `useRealAPI` to switch between real backend and mock data. Distinguishes between text responses and visual payloads.

### 2. GenerativeWidgetView (View Factory)
* **Responsibility:** The "Generative UI" engine. Takes a `VisualComponent` enum and returns the corresponding SwiftUI View.
* **Capabilities:** Can render `BurndownWidgetView`, `BudgetSliderView`, or `SankeyFlowView` on demand.

### 3. APIService / MockService (Network Layer)
* **Responsibility:** Actor-isolated services for thread-safe async communication with the backend.
* **Key Logic:** `APIService` connects to Flask backend (localhost:5000). `MockService` provides simulated responses for offline development.

<!-- ### 5. BankLinkManager
* **Responsibility:** Wraps the external banking SDK (e.g., Plaid/Teller).
* **Key Logic:** Securely handles OAuth tokens and refreshes transaction data in the background. -->

## Key Data Structures

```swift
// The hybrid response object from the AI
struct AssistantResponse: Codable {
    let textMessage: String
    let visualPayload: VisualComponent? // Optional: Only present if AI wants to show a chart
}

enum VisualComponent: Codable {
    case budgetBurndown(data: [BurndownDataPoint])
    case sankeyFlow(nodes: [SankeyNode])
    case interactiveSlider(category: String, current: Double, max: Double)
    case burndownChart(spent: Double, budget: Double, idealPace: Double)
    case budgetSlider(category: String, current: Double, max: Double)
}

struct Transaction: Identifiable, Codable {
    let id: UUID
    let amount: Decimal
    let merchant: String
    let category: BudgetCategory
    let date: Date
}