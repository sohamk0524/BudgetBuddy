# Server Architecture (Python - FastAPI)

## High-Level Overview
The backend acts as the "Brain." It orchestrates the flow between the user, the database, the Banking APIs, and the LLM. It is built using **FastAPI** for high performance and easy async handling.

## Key Modules

### 1. The Orchestrator (Agent Logic)
* **Responsibility:** The core decision maker. Receives user input, decides which tools to call (e.g., "GetTransactions", "UpdateBudget"), and formats the final prompt for the LLM.
* **Tech:** LangChain or custom Python logic.

### 2. Banking Integrator
* **Responsibility:** Interacts with Plaid/Teller APIs.
* **Key Logic:** Normalizes messy transaction data (e.g., converting "MCDONALDS 442" -> "McDonalds" | Category: "Food").

### 3. Prompt Engine
* **Responsibility:** Stores the system prompts and persona definitions.
* **Key Logic:** Dynamically injects context (e.g., "User has $500 in bank") into the system prompt before sending to the LLM.

### 4. UserProfile Service
* **Responsibility:** Auth (Supabase/Firebase Auth) and user settings.
* **Key Logic:** Stores privacy preferences and encryption keys.

### 5. API Gateway
* **Responsibility:** Exposes REST endpoints to the iOS client.
* **Endpoints:**
    * `POST /chat`: Main interaction point.
    * `GET /sync`: Triggers a bank data refresh.

## Key Data Interfaces (JSON)

**Chat Request:**
```json
{
  "user_id": "12345",
  "message": "Can I afford dinner?",
  "current_context": { "lat": 34.05, "long": -118.25 }
}