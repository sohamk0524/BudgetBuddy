# Instructions for Claude Code 

You are an expert iOS Developer specializing in SwiftUI, MVVM, and clean architecture. I am building "BudgetBuddy," an AI-powered finance app.

I have provided you with three context files:
1. `overview.md`: The product vision.
2. `client_architecture.md`: The iOS technical structure.
3. `server_architecture.md`: The backend structure (for context on data types).

**Your Goal:**
Generate the file structure and Swift code for a **UI-First Prototype** of the iOS Client. We are NOT connecting to a real backend yet. We will use **Mock Data** to simulate the AI's response.

**Core Requirement:**
The app must demonstrate the "Hybrid Interface" described in the architecture:
1.  A Chat Interface where messages appear.
2.  A mechanism to render a **Visual Component** (like a dummy chart) inside the chat stream or in a dedicated pane when the "AI" responds.

**Architecture Constraints:**
* **UI Framework:** SwiftUI.
* **State Management:** Use the `@Observable` macro (Observation framework).
* **Separation:** Keep the Data Models (`structs`) separate from the Views.

**Required Files to Generate:**

1.  **`BudgetBuddyApp.swift`**: The main entry point.
2.  **`Models.swift`**:
    * Define the `AssistantResponse` and `VisualComponent` enums exactly as shown in `client_architecture.md`.
    * Include a `MessageType` enum (User vs. AI).
3.  **`MockService.swift`**:
    * Create a class that simulates an API call.
    * Function: `sendMessage(text: String) async throws -> AssistantResponse`
    * Implementation: Wait 1 second (simulated network delay), then return a hardcoded `AssistantResponse` that contains **both** text and a `.budgetBurndown` visual component.
4.  **`ChatViewModel.swift`**:
    * Call `MockService` and append messages to a published `messages` array.
5.  **`Components/ChatBubbleView.swift`**:
    * A view to render text messages.
6.  **`Components/BurndownChartView.swift`**:
    * A simple SwiftUI view using `Charts` framework (or simple Shapes) to render dummy data.
7.  **`ChatView.swift`**:
    * The main screen. It should iterate through the `messages`.
    * **Crucial:** Switch on the `visualPayload`. If the message has a visual payload, render `BurndownChartView` below the text.

**Output Format:**
Please provide the code for each file in a separate code block, labeled with the filename.