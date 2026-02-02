# Server Architecture (Python - Flask)

## High-Level Overview
The backend acts as the "Brain." It orchestrates the flow between the user and the LLM (Ollama running locally). It is built using **Flask** with CORS enabled for iOS simulator communication.

## Key Modules

### 1. The Orchestrator (Agent Logic)
* **Responsibility:** The core decision maker. Receives user input, decides which tools to call (e.g., `get_budget_overview`, `get_spending_status`), and formats the final prompt for the LLM.
* **Tech:** Custom Python logic with OpenAI SDK client for Ollama (llama3.2:3b model). Uses keyword filtering to prevent over-eager tool calls on non-financial queries.

<!-- ### 2. Banking Integrator
* **Responsibility:** Interacts with Plaid/Teller APIs.
* **Key Logic:** Normalizes messy transaction data (e.g., converting "MCDONALDS 442" -> "McDonalds" | Category: "Food"). -->

### 2. Prompt Engine
* **Responsibility:** Stores the system prompts and persona definitions.
* **Key Logic:** Dynamically injects context (e.g., "User has $500 in bank") into the system prompt before sending to the LLM.

### 3. UserProfile Service
* **Responsibility:** Auth (Supabase/Firebase Auth) and user settings.
* **Key Logic:** Stores privacy preferences and encryption keys.

### 4. API Gateway (app.py)
* **Responsibility:** Exposes REST endpoints to the iOS client.
* **Endpoints:**
    * `POST /chat`: Main interaction point. Returns `AssistantResponse` with text and optional visual payload.
    * `GET /health`: Health check endpoint.

## Key Data Interfaces (JSON)

**Chat Request:**
```json
{
  "userId": "12345",
  "message": "Can I afford dinner?"
}