# Task: Implement Real-Time School-Specific RAG via Web Search

## 1. Goal
Create a standalone backend service in our Flask app that allows students to get financial advice tailored to their specific university (discounts, scholarships, local deals). Instead of local docs, use the Tavily Search API to fetch real-time web data.

This is a self-contained feature — it should NOT be integrated into the existing chat agent or orchestrator. The core logic should live in its own service file so it can be easily pulled into the agent tool system later.

## 2. Technical Context
- **Backend:** Flask (Python), existing app in `BudgetBuddyBackend/app.py`
- **LLM:** Use `litellm` (already in requirements.txt) — NOT the `anthropic` SDK directly. Route calls through `litellm.completion(model="claude-sonnet-4-5", ...)` to stay consistent with the rest of the codebase.
- **Search Tool:** Tavily API (use `tavily-python` library)
- **Database:** The user's school is already stored in `FinancialProfile.school` (see `db_models.py`). Values are UC campus slugs like `"uc_davis"`, `"uc_berkeley"`, etc.
- **Frontend:** Swift (iOS) — this service will be called as an API endpoint from the app.

## 3. Core Requirements
Implement a service function `get_school_advice(user_query, school_name)` in a new file `BudgetBuddyBackend/services/school_rag.py`:

### A. Search Query Construction
- Don't just search the user's query verbatim. Rewrite it to be school-specific and financially relevant.
- Use litellm to generate the optimized search query (a quick, cheap call).
- Example: If query is "cheap coffee" and school is "UC Davis", search for "best student coffee discounts and deals near UC Davis 2026".
- Example: If query is "scholarships" and school is "UC Berkeley", search for "UC Berkeley scholarships for current students financial aid 2026".

### B. Retrieval (Tavily)
- Use Tavily's `search` method with `search_depth="advanced"`.
- Set `include_answer=True` to get Tavily's own synthesized answer as additional context.
- Pass the search results (content snippets + URLs) to the LLM for synthesis.

### C. Synthesis (Claude via litellm)
- Pass the search results to Claude with a system prompt like:
  > "You are a student financial navigator for {school_name}. Use the provided search results to answer the student's query: '{user_query}'.
  > - Be specific: Name the shops, amounts, and locations.
  > - Cite sources: Reference the source URLs inline when mentioning specific deals or facts.
  > - Fallback: If no school-specific deals are found, provide general student saving tips for that category.
  > - Keep responses concise and mobile-friendly (short paragraphs, bullet points)."
- Use `litellm.completion(model="claude-sonnet-4-5", messages=[...])` for this call.

## 4. Implementation Steps

### Step 1: Dependency
Add `tavily-python` to `requirements.txt`. Do NOT add `anthropic` — we use `litellm` for all LLM calls.

### Step 2: Environment
Assume `TAVILY_API_KEY` is in `.env` (already loaded via `python-dotenv` in `app.py`).

### Step 3: Service File
Create `BudgetBuddyBackend/services/school_rag.py` with:
- `get_school_advice(user_query: str, school_name: str) -> dict` — the core function
- Returns `{"answer": str, "sources": [{"title": str, "url": str}]}`
- Handles errors gracefully (Tavily down, no results found, etc.)

### Step 4: Flask Endpoint
Add a POST route `/api/school-advice` in `app.py` that:
- Accepts JSON body: `{"query": str, "user_id": int, "school_name": str (optional)}`
- If `school_name` is not provided, pulls it from `FinancialProfile.school` for the given `user_id`
- Returns: `{"answer": str, "sources": [{"title": str, "url": str}]}`
- Returns 400 if no query provided, 404 if user not found, 500 on internal errors

### Step 5: School Name Mapping
The `FinancialProfile.school` field stores slugs like `"uc_davis"`. Create a simple mapping dict to convert these to full names for better search results:
```python
SCHOOL_DISPLAY_NAMES = {
    "uc_davis": "UC Davis",
    "uc_berkeley": "UC Berkeley",
    "ucla": "UCLA",
    "uc_san_diego": "UC San Diego",
    # ... etc
}
```

## 5. Constraints
- Keep it simple: No vector database or caching is required for this version.
- Ensure the response is formatted cleanly for a mobile (Swift) UI.
- Do NOT modify the existing orchestrator, agent, or tools files.
- The service should be stateless — no database writes, just read the user's school and return advice.
