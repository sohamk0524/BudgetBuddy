# Client Architecture (iOS - SwiftUI)

## High-Level Overview
The iOS client uses a modern **MVVM (Model-View-ViewModel)** architecture with **SwiftUI**. The core differentiator is the "Generative UI" engine, which renders native SwiftUI views based on JSON payloads received from the LLM.

## Key Modules

### 1. ChatOrchestrator (ViewModel)
* **Responsibility:** Manages the conversation state. It sends user input to the backend and handles the parsing of the response.
* **Key Logic:** Distinguishes between simple text responses and "Command Payloads" (responses that trigger a UI change).

### 2. DynamicViewRenderer (View Factory)
* **Responsibility:** The "Generative UI" engine. It takes a structured data object (e.g., `VisualPlanType`) and returns the corresponding SwiftUI View.
* **Capabilities:** Can render `SankeyDiagramView`, `BurndownChartView`, or `BudgetSliderView` on demand.

### 3. DataRepository (Model Layer)
* **Responsibility:** The single source of truth. Manages `SwiftData` (local persistence) and interacts with the API Service.
* **Key Logic:** Optimistic UI updates (updating the UI immediately before the server confirms).

### 4. LLMService (Network Layer)
* **Responsibility:** Handles secure communication with the backend AI agent.
* **Key Logic:** Streaming response handling (typing effect) and error management for API hallucinations.

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
    case budgetBurndown(data: [Date: Double])
    case sankeyFlow(nodes: [SankeyNode])
    case interactiveSlider(category: String, current: Double, max: Double)
}

struct Transaction: Identifiable, Codable {
    let id: UUID
    let amount: Decimal
    let merchant: String
    let category: BudgetCategory
    let date: Date
}