# Server Architecture (Python - Flask)

## High-Level Overview
The backend acts as the "Brain." It orchestrates the flow between the user and the LLM (Ollama running locally). It is built using **Flask** with SQLAlchemy for persistence and CORS enabled for iOS simulator communication. The app exposes a set of REST endpoints covering auth, onboarding, budget plan generation, chat, and bank statement analysis.

---

## Database Layer

* **ORM:** SQLAlchemy (via `flask-sqlalchemy`), backed by a local SQLite database (`budgetbuddy.db`).
* **Models (defined in `db_models.py`):**
    * `User` — Stores account credentials (email + hashed password via Werkzeug) and optional `name`. Has a one-to-one relationship to `FinancialProfile`.
    * `FinancialProfile` — Holds the user's onboarded financial context: income, expenses, housing situation, debt types (stored as a JSON string), financial personality, primary goal, and a named savings goal with a target amount.
    * `BudgetPlan` — Stores a generated spending plan as a JSON blob, with a `created_at` timestamp and an optional `month_year` field. Linked to a user by foreign key.
    * `SavedStatement` — User's uploaded bank statement with parsed data, LLM analysis, and derived financial metrics.
    * `PlaidItem` — Represents a user's linked bank connection via Plaid. Stores encrypted access token, institution info, and transaction sync cursor.
    * `PlaidAccount` — Individual bank account within a PlaidItem (checking, savings, etc.) with balance data.
    * `Transaction` — Individual transaction from Plaid with category, amount, date, and merchant info.
    * `UserCategoryPreference` — User's pinned spending category preferences for the homepage display.

---

## Key Modules

### 1. The Orchestrator (`services/orchestrator.py`)
* **Responsibility:** The core decision maker for the chat flow. Receives a raw user message and a `userId`, decides which tools or context to pull in, and returns a structured `AssistantResponse`.
* **Interface:** `process_message(message: str, user_id: str) -> AssistantResponse`
* **Tech:** Custom Python logic with OpenAI SDK client pointed at Ollama (llama3.2:3b model). Uses keyword filtering to prevent over-eager tool calls on non-financial queries.

### 2. Statement Analyzer (`services/statement_analyzer.py`)
* **Responsibility:** Parses an uploaded bank statement file (PDF or CSV) and returns a structured analysis with a text summary and an optional visual payload.
* **Interface:** `analyze_statement(file_content: bytes, filename: str) -> AssistantResponse`

### 3. Plan Generator (`services/plan_generator.py`)
* **Responsibility:** Takes a user's deep-dive financial data, generates a personalized monthly spending plan via the LLM, and persists it.
* **Interfaces:**
    * `generate_plan(user_id: int, deep_dive_data: dict) -> dict` — Produces the plan object and an accompanying text message / visual payload.
    * `save_plan_to_db(user_id: int, plan: dict)` — Writes the generated plan into the `BudgetPlan` table.

### 4. Prompt Engine
* **Responsibility:** Stores system prompts and persona definitions.
* **Key Logic:** Dynamically injects context (e.g., user's income, goal, current balance) into the system prompt before sending to the LLM.

### 5. Plaid Service (`services/plaid_service.py`)
* **Responsibility:** Handles all Plaid API interactions — creating link tokens, exchanging public tokens, fetching accounts/transactions, syncing new transactions, and removing items.
* **Key Logic:** Access tokens are encrypted at rest using Fernet encryption. Supports sandbox and production environments via `PLAID_ENV`.

### 6. Nudge Generator (`services/nudge_generator.py`)
* **Responsibility:** Rules-based (no LLM) smart nudge generation. Compares actual spending from Plaid transactions against budget plan allocations.
* **Nudge Types:** `spending_reduction` (over budget), `positive_reinforcement` (under budget), `goal_reminder` (savings progress).
* **Interface:** `generate_nudges(user_id: int) -> List[Dict]` — Returns top 5 nudges sorted by impact.

### 7. Auth & Security
* **Responsibility:** User registration and login.
* **Key Logic:** Passwords are hashed at rest using Werkzeug's `generate_password_hash` (PBKDF2 by default). Authentication is stateless — the server returns the user's database `id` as a token, which the iOS client sends with subsequent requests.

---

## API Gateway (`app.py`) — Endpoints

| Method | Route | Purpose |
|---|---|---|
| `GET` | `/` | Welcome / API root |
| `GET` | `/health` | Health check |
| `POST` | `/register` | Create a new user account (optionally accepts `name`) |
| `POST` | `/login` | Authenticate and return user token + profile status + name |
| `POST` | `/onboarding` | Save or update a user's financial profile (accepts `name`) |
| `POST` | `/generate-plan` | Run the plan generator with deep-dive data |
| `GET` | `/get-plan/<user_id>` | Retrieve the user's most recent saved plan |
| `POST` | `/chat` | Main chat interaction with the AI assistant |
| `POST` | `/upload-statement` | Upload and analyze a PDF or CSV bank statement |
| `GET` | `/user/financial-summary` | Get financial summary from saved statement |
| `DELETE` | `/user/statement` | Delete user's saved statement |
| `GET` | `/user/profile/<user_id>` | Fetch user profile, financial info, and linked accounts |
| `PUT` | `/user/profile/<user_id>` | Update user profile fields (partial update) |
| `GET` | `/user/top-expenses/<user_id>` | Aggregate top spending categories (Plaid or statement) |
| `GET` | `/user/category-preferences/<user_id>` | Get user's pinned category preferences |
| `PUT` | `/user/category-preferences/<user_id>` | Set pinned categories |
| `GET` | `/user/nudges/<user_id>` | Get rules-based smart nudges |
| `POST` | `/plaid/link-token` | Create a Plaid Link token |
| `POST` | `/plaid/exchange-token` | Exchange public token for access token + fetch data |
| `GET` | `/plaid/accounts/<user_id>` | Get all linked accounts |
| `GET` | `/plaid/transactions/<user_id>` | Get transactions with date filtering + pagination |
| `POST` | `/plaid/sync/<user_id>` | Sync new transactions for linked accounts |
| `DELETE` | `/plaid/unlink/<user_id>/<item_id>` | Unlink a bank connection |

---

## Key Data Interfaces (JSON)

### Auth — Register / Login Request
```json
{
  "email": "user@example.com",
  "password": "password123"
}
```

### Auth — Login Response
```json
{
  "token": 1,
  "hasProfile": true,
  "name": "Alex"
}
```

### Onboarding Request
```json
{
  "userId": 1,
  "income": 5000.0,
  "expenses": 2000.0,
  "goalName": "Car",
  "goalTarget": 10000.0,
  "incomeFrequency": "monthly",
  "housingSituation": "rent",
  "debtTypes": ["student_loans", "credit_cards"],
  "financialPersonality": "balanced",
  "primaryGoal": "emergency_fund"
}
```

### Chat Request
```json
{
  "userId": "123",
  "message": "Can I afford dinner?"
}
```

### Chat Response
```json
{
  "textMessage": "Based on your budget...",
  "visualPayload": { "..." : "..." }
}
```

### Generate-Plan Request (deep-dive payload)
```json
{
  "userId": 1,
  "deepDiveData": {
    "fixedExpenses": {
      "rent": 1200,
      "utilities": 150,
      "subscriptions": [{ "name": "Netflix", "amount": 15 }]
    },
    "variableSpending": {
      "groceries": 400,
      "transportation": { "type": "car", "gas": 150, "insurance": 100 },
      "diningEntertainment": 200
    },
    "upcomingEvents": [
      { "name": "Wedding", "date": "2026-06-15", "cost": 800, "saveGradually": true }
    ],
    "savingsGoals": [
      { "name": "Emergency fund", "target": 1000, "current": 150, "priority": 1 }
    ],
    "spendingPreferences": {
      "spendingStyle": 0.3,
      "priorities": ["savings", "security"],
      "strictness": "moderate"
    }
  }
}
```

### Generate-Plan Response
```json
{
  "textMessage": "Your personalized plan is ready!",
  "plan": { "..." : "..." },
  "visualPayload": { "..." : "..." }
}
```

### Get-Plan Response
```json
{
  "hasPlan": true,
  "plan": { "..." : "..." },
  "createdAt": "2026-02-01T12:00:00",
  "monthYear": "2026-02"
}
```

### Upload-Statement
* **Request:** `multipart/form-data` with a `file` field (PDF or CSV).
* **Response:** Same shape as the chat response (`textMessage` + optional `visualPayload`).

### User Profile Response (`GET /user/profile/<id>`)
```json
{
  "name": "Alex",
  "email": "user@example.com",
  "profile": {
    "age": 25,
    "occupation": "employed",
    "monthlyIncome": 5000.0,
    "incomeFrequency": "monthly",
    "financialPersonality": "balanced",
    "primaryGoal": "emergency_fund"
  },
  "plaidItems": [
    {
      "itemId": "item_abc123",
      "institutionName": "Chase",
      "status": "active",
      "accounts": [{ "accountId": "acc_1", "name": "Checking", "type": "depository", "balanceCurrent": 5000 }]
    }
  ]
}
```

### Top Expenses Response (`GET /user/top-expenses/<id>`)
```json
{
  "source": "plaid",
  "topExpenses": [
    { "category": "FOOD_AND_DRINK", "amount": 450.50, "transactionCount": 28 }
  ],
  "totalSpending": 2500.00,
  "period": 30
}
```

### Nudges Response (`GET /user/nudges/<id>`)
```json
{
  "nudges": [
    {
      "type": "spending_reduction",
      "title": "Food Over Budget",
      "message": "You've spent $450 of your $300 Food budget.",
      "category": "Food",
      "potentialSavings": 150.00
    }
  ]
}

---

## Request / Response Flow (Chat)

```
iOS Client
    │
    │  POST /chat  { message, userId }
    ▼
app.py  ──►  Orchestrator.process_message()
                  │
                  ├── pulls user context (profile, plan) from DB
                  ├── keyword filters → decides tool calls
                  ├── injects context via Prompt Engine
                  └── calls Ollama (llama3.2:3b) via OpenAI SDK
                  │
                  ▼
            AssistantResponse  { textMessage, visualPayload }
    │
    ▼
iOS Client
```
