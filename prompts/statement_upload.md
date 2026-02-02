# Bank Statement Upload Feature

We are adding a feature to BudgetBuddy where users can upload their bank statements for LLM analysis. The LLM will parse the statement, extract transactions, and provide financial insights. **Uploaded statements are persisted to the backend database** so users can reference them later and the Wallet tab can display derived financial metrics.

---

## Statement Persistence

### What Gets Stored
Each user has **one saved statement** (new uploads replace the previous). The backend stores:

1. **Raw File:** The original PDF/CSV file (for re-analysis or download)
2. **Parsed Data:** Extracted transactions and metadata in structured format
3. **LLM Analysis:** The full JSON response from the LLM (friendly_summary, categories, insights)

### Database Schema

```python
class SavedStatement:
    id: str                    # UUID
    user_id: str               # References the authenticated user
    filename: str              # Original filename
    file_type: str             # "pdf" or "csv"
    raw_file: bytes            # The original file content
    parsed_data: dict          # Extracted transactions and metadata
    llm_analysis: dict         # Full LLM JSON response

    # Derived financial metrics (computed from parsed_data/llm_analysis)
    ending_balance: float      # Account balance at end of statement period
    total_income: float        # Sum of positive transactions
    total_expenses: float      # Sum of negative transactions
    statement_start_date: date # First transaction date
    statement_end_date: date   # Last transaction date

    created_at: datetime
    updated_at: datetime
```

### Replacement Behavior
When a user uploads a new statement:
1. Delete the existing statement record (if any) for that user
2. Delete the old raw file from storage
3. Create a new statement record with the new data

---

## Wallet Tab Integration

### Derived Metrics

The Wallet tab displays financial metrics derived from the saved statement:

**Net Worth:**
```
net_worth = ending_balance
```
Uses the ending balance from the most recent statement as a simple proxy for net worth. (Future: support multiple accounts and liability tracking)

**Safe to Spend:**
```
safe_to_spend = net_worth + net_income - essential_expenses - savings_target

where:
  net_worth = ending_balance from statement
  net_income = total_income from statement (deposits/credits)
  essential_expenses = fixed_expenses from user's FinancialProfile (set during onboarding)
  savings_target = savings_goal_target from user's FinancialProfile (set during onboarding)
```
This calculates how much the user can safely spend after accounting for their income, essential bills, and savings goals.

### New Endpoint: `GET /user/financial-summary`

Returns the derived metrics for the Wallet tab. Requires authentication.

**Response:**
```json
{
  "has_statement": true,
  "net_worth": 2450.00,
  "safe_to_spend": 850.00,
  "statement_info": {
    "filename": "chase_jan_2024.pdf",
    "statement_period": "2024-01-01 to 2024-01-31",
    "uploaded_at": "2024-02-01T10:30:00Z"
  },
  "spending_breakdown": [
    {"category": "Food", "amount": 320.00},
    {"category": "Transportation", "amount": 150.00}
  ]
}
```

If no statement is saved:
```json
{
  "has_statement": false,
  "net_worth": null,
  "safe_to_spend": null,
  "statement_info": null,
  "spending_breakdown": null
}
```

### Wallet UI Changes

**WalletView.swift:**
- Fetch financial summary on appear via `GET /user/financial-summary`
- Update `NetWorthCard` to display `net_worth` from API (or placeholder if no statement)
- Add new `SafeToSpendCard` displaying `safe_to_spend` value
- Add new `LinkedStatementCard` showing:
  - Statement filename and upload date
  - "View Details" button to see spending breakdown
  - "Upload New" button to replace with a new statement
- If no statement linked, show prompt to upload one

**New/Updated Files:**
- `WalletView.swift`: Integrate with financial summary API
- `WalletViewModel.swift` (new): State management for wallet data
- `APIService.swift`: Add `getFinancialSummary()` function

---

## iOS Client Changes

### 1. Statement Upload UI
* Add a way to trigger file upload (e.g., attachment button in chat input or dedicated upload screen).
* Use `fileImporter` modifier to present the system file picker.
* Supported file types: PDF (`.pdf`) and CSV (`.csv`).
* **New:** Also accessible from `LinkedStatementCard` in Wallet tab.

### 2. Upload Flow
* **Loading State:** Show progress indicator while uploading and analyzing.
* **Error Handling:** Display error if file is too large, wrong format, or analysis fails.
* **Results Display:** Show the AI's analysis as a chat message with an optional visual payload.
* **New:** After successful upload, notify `WalletViewModel` to refresh financial summary.

### 3. New/Updated Files
* `ChatView.swift`: Add file picker trigger and `fileImporter` modifier.
* `ChatViewModel.swift`: Add `uploadStatement(url: URL)` function to handle file upload.
* `APIService.swift`: Add `uploadStatement(fileURL: URL)` function for multipart upload.
* **New:** `WalletViewModel.swift`: Fetch and cache financial summary.

---

## Backend Changes

### 1. Updated Endpoint: `POST /upload-statement`
* **Content-Type:** `multipart/form-data`
* **Request:** File upload with field name `file`. Requires authentication.
* **Response:** Same `AssistantResponse` format with text analysis and optional visual payload.
* **New Behavior:** Saves statement to database after analysis, replacing any existing statement for the user.

```python
@app.route("/upload-statement", methods=["POST"])
@require_auth
def upload_statement():
    user_id = get_current_user_id()
    file = request.files.get("file")

    # Parse and analyze
    parsed_data, llm_analysis = analyze_statement(file)

    # Save to database (replaces existing)
    save_statement(user_id, file, parsed_data, llm_analysis)

    # Return AssistantResponse
    return build_response(llm_analysis)
```

### 2. New Endpoint: `GET /user/financial-summary`
* Returns derived metrics for the authenticated user's saved statement.
* See response format in "Wallet Tab Integration" section above.

```python
@app.route("/user/financial-summary", methods=["GET"])
@require_auth
def get_financial_summary():
    user_id = get_current_user_id()
    statement = get_saved_statement(user_id)

    if not statement:
        return {"has_statement": False, ...}

    return {
        "has_statement": True,
        "net_worth": compute_net_worth(statement),
        "safe_to_spend": compute_safe_to_spend(statement),
        "statement_info": {...},
        "spending_breakdown": statement.llm_analysis.get("top_categories", [])
    }
```

### 3. New Endpoint: `DELETE /user/statement`
* Deletes the user's saved statement.
* Returns 204 No Content on success.

### 4. Statement Parsing
* **CSV:** Parse rows into transactions (date, description, amount).
* **PDF:** Extract text using a library (e.g., `pdfplumber` or `PyPDF2`), then parse transaction patterns.

### 5. LLM Analysis Prompt
Send extracted transactions to the LLM with the following system prompt:

```
You are a financial data extraction and analysis assistant.

Your task is to parse a bank statement and return structured, machine-readable output.
Be precise, conservative, and do not hallucinate missing data.
If information is ambiguous or missing, return null and explain why.

Follow these steps strictly:
1. Identify statement metadata
2. Extract all transactions
3. Normalize amounts, dates, and categories
4. Produce financial summaries and insights

Return output in valid JSON only.
```

And use the following user prompt to analyze the transaction:

```
Here is a bank statement.

<BEGIN_STATEMENT>
{{BANK_STATEMENT_TEXT}}
<END_STATEMENT>

Please:
1. Extract the statement details (bank, dates, balances).
2. List all transactions with:
   - date
   - description
   - amount (negative = money spent, positive = money received)
3. Group each transaction into a simple spending category that a student would understand.
4. Summarize spending behavior in a clear, non-judgmental way.

Rules:
- Do not guess or invent missing information.
- If something is unclear, leave it blank or say "unknown".
- Use plain language suitable for a college student.
- Return valid JSON only.

Return JSON with the following top-level keys:
- metadata (including ending_balance, statement_start_date, statement_end_date)
- transactions
- total_income
- total_expenses
- top_categories
- behavior_summary
- warnings
- friendly_summary (a conversational 2-3 sentence summary to show the user in chat)
```

### 6. Building the AssistantResponse
After parsing the LLM's JSON output:
* Use `friendly_summary` as the `textMessage` field.
* Use `transactions` and `behavior_summary` to build the visual payload.

### 7. Visual Payload Options
Based on analysis, return one of:
* `sankeyFlow`: Income → expense category breakdown
* `burndownChart`: Spending pace over the statement period
* New component (if needed): Category pie chart or transaction list

---

## Data Flow

### Upload Flow
1. User taps upload button → file picker opens
2. User selects PDF/CSV → `ChatViewModel.uploadStatement(url:)` called
3. `APIService` sends multipart POST to `/upload-statement` (with auth token)
4. Backend parses file → extracts transactions → sends to LLM
5. LLM returns analysis JSON
6. **Backend saves statement to database (replacing any existing)**
7. Backend returns `AssistantResponse` with text and visual payload
8. iOS displays analysis in chat with rendered widget
9. **iOS notifies `WalletViewModel` to refresh financial summary**

### Wallet Load Flow
1. User navigates to Wallet tab
2. `WalletViewModel` calls `GET /user/financial-summary`
3. If statement exists: display Net Worth, Safe to Spend, and statement info
4. If no statement: show prompt to upload one

---

## Dependencies

**Backend (add to requirements.txt):**
```
pdfplumber>=0.9.0  # For PDF text extraction
```

**Database:**
- SQLite for local development
- PostgreSQL recommended for production
- File storage for raw PDFs/CSVs (local filesystem or S3)

---

## Future Enhancements (Out of Scope for Now)
* Support multiple statements/accounts per user
* Liability tracking (credit cards reduce net worth)
* Link transactions to existing budget categories
* Support for bank-specific statement formats
* Automatic recurring transaction detection
* Historical statement tracking and trend analysis
* Bill detection for more accurate "Safe to Spend"
