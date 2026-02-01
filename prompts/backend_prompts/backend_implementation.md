# Instructions BudgetBuddy Backend Implementation (Flask)

**Context:**
We are building the backend for "BudgetBuddy", an AI finance app.
* **Current State:** A basic Flask app exists.
* **Frontend:** A Swift iOS app expecting specific JSON payloads for "Generative UI" widgets (Sankey Diagrams, Burndown Charts).

**The Goal:**
Expand the Flask app to serve the `/chat` endpoint. It must act as the "Orchestrator," analyzing user input and deciding whether to return a simple text response or a complex visual payload.
You can look at overview.md and server_architecture.md and client_architecture.md for a refresher of the overall goal

**Critical Constraint: Data Contracts**
The iOS app uses Swift `Codable` to parse responses. You **MUST** adhere to the JSON structure defined below.
* **Keys:** Use `camelCase` for all JSON keys (Python uses `snake_case` internally, so you must serialize it manually or use a helper).
* **Enums:** The iOS app expects the `VisualComponent` enum to be serialized as a single-key object (e.g., `{"sankeyFlow": { ... data ... }}`).

---

## Required File Generation/Updates

Please generate/update the following files in the backend directory.

### 1. `app.py` (The Entry Point)
* Ensure a route `POST /chat` exists.
* **Logic:**
    1.  Parse the JSON request body (Expect: `{"message": "user text", "userId": "123"}`).
    2.  Call `OrchestratorService.process_message(user_text)`.
    3.  Return the result as JSON.
* **CORS:** Enable CORS (using `flask_cors`) so the iOS simulator can talk to `localhost`.

### 2. `models.py` (The Data Contracts)
Define the Python classes/dicts that mirror the Swift structs.

* **`SankeyLink`**:
    * `label` (str), `amount` (float), `colorHex` (str).
* **`VisualPayload`** (Helper to format the enum):
    * Should have a method to dump to dict: `{"sankeyFlow": {...}}` or `{"burndownChart": {...}}`.
* **`AssistantResponse`**:
    * `textMessage` (str)
    * `visualPayload` (Optional[dict])

### 3. `services/orchestrator.py` (The "Brain")
This service simulates the AI deciding which tool to use.
* **Function:** `process_message(text: str) -> AssistantResponse`
* **Logic (Keyword Detection for Prototype):**
    * **Case A (The Plan):** If text contains "plan", "overview", or "flow":
        * Return text: "Here is your flow for November."
        * Return Payload: `sankeyFlow` with generic data (Income: 5000, Expenses: Rent 2000/Food 800/Savings 1000).
    * **Case B (Spending Check):** If text contains "afford", "can I buy", or "status":
        * Return text: "That purchase is risky. You are pacing above budget."
        * Return Payload: `burndownChart` (spent: 1200, budget: 2000, idealPace: 1000).
    * **Case C (Default):** All other text:
        * Return text: "I can help you with that. Try asking to see your 'Plan' or checking your 'Status'."
        * Return Payload: `null`.

### 4. `services/data_mock.py`
* Create a simple helper file that returns the hardcoded colors and data values so they aren't cluttering the logic file.
* Use the hex codes from our design system:
    * Teal: `#2DD4BF`, Purple: `#A855F7`, Coral: `#F43F5E`, Slate: `#1E293B`.

---

## JSON Response Examples (Reference)

Your Python code must output JSON exactly like this:

**Scenario 1: Burndown**
```json
{
  "textMessage": "Careful, you are overspending.",
  "visualPayload": {
    "burndownChart": {
      "spent": 1250.0,
      "budget": 2000.0,
      "idealPace": 900.0
    }
  }
}

Decide if there is anything missing on the frontend, and implement it if necessary