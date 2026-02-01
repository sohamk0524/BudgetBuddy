# Bank Statement Upload Feature

We are adding a feature to BudgetBuddy where users can upload their bank statements for LLM analysis. The LLM will parse the statement, extract transactions, and provide financial insights.

## iOS Client Changes

### 1. Statement Upload UI
* Add a way to trigger file upload (e.g., attachment button in chat input or dedicated upload screen).
* Use `fileImporter` modifier to present the system file picker.
* Supported file types: PDF (`.pdf`) and CSV (`.csv`).

### 2. Upload Flow
* **Loading State:** Show progress indicator while uploading and analyzing.
* **Error Handling:** Display error if file is too large, wrong format, or analysis fails.
* **Results Display:** Show the AI's analysis as a chat message with an optional visual payload.

### 3. New/Updated Files
* `ChatView.swift`: Add file picker trigger and `fileImporter` modifier.
* `ChatViewModel.swift`: Add `uploadStatement(url: URL)` function to handle file upload.
* `APIService.swift`: Add `uploadStatement(fileURL: URL)` function for multipart upload.

---

## Backend Changes

### 1. New Endpoint: `POST /upload-statement`
* **Content-Type:** `multipart/form-data`
* **Request:** File upload with field name `file`.
* **Response:** Same `AssistantResponse` format with text analysis and optional visual payload.

```python
@app.route("/upload-statement", methods=["POST"])
def upload_statement():
    file = request.files.get("file")
    # Parse and analyze
    # Return AssistantResponse
```

### 2. Statement Parsing
* **CSV:** Parse rows into transactions (date, description, amount).
* **PDF:** Extract text using a library (e.g., `pdfplumber` or `PyPDF2`), then parse transaction patterns.

### 3. LLM Analysis Prompt
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
- metadata
- transactions
- behavior_summary
- warnings
- friendly_summary (a conversational 2-3 sentence summary to show the user in chat)
```

### 4. Building the AssistantResponse
After parsing the LLM's JSON output:
* Use `friendly_summary` as the `textMessage` field.
* Use `transactions` and `behavior_summary` to build the visual payload.

### 5. Visual Payload Options
Based on analysis, return one of:
* `sankeyFlow`: Income → expense category breakdown
* `burndownChart`: Spending pace over the statement period
* New component (if needed): Category pie chart or transaction list

---

## Data Flow

1. User taps upload button → file picker opens
2. User selects PDF/CSV → `ChatViewModel.uploadStatement(url:)` called
3. `APIService` sends multipart POST to `/upload-statement`
4. Backend parses file → extracts transactions → sends to LLM
5. LLM returns analysis text + suggested visual
6. Backend returns `AssistantResponse` with text and visual payload
7. iOS displays analysis in chat with rendered widget

---

## Dependencies

**Backend (add to requirements.txt):**
```
pdfplumber>=0.9.0  # For PDF text extraction
```

---

## Future Enhancements (Out of Scope for Now)
* Persist uploaded statements to database
* Link transactions to existing budget categories
* Support for bank-specific statement formats
* Automatic recurring transaction detection
