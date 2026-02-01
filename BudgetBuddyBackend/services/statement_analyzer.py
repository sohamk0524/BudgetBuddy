"""
Statement Analyzer Service - Parses and analyzes bank statements.
"""

import csv
import io
import json
from typing import Optional, Dict, Any

from models import AssistantResponse, VisualPayload, SankeyNode
from services.llm_service import BudgetBuddyAgent

# Use a larger model for complex analysis if available
agent = BudgetBuddyAgent(model="llama3.2:3b")

SYSTEM_PROMPT = """You are BudgetBuddy, a friendly financial assistant helping college students understand their spending.

Analyze bank statements and provide helpful, conversational insights. Be encouraging and non-judgmental."""

USER_PROMPT_TEMPLATE = """Here is a bank statement to analyze:

<BEGIN_STATEMENT>
{statement_text}
<END_STATEMENT>

Analyze this statement and respond with JSON containing these fields:

{{
  "friendly_summary": "A conversational 2-3 sentence summary for the user. Be warm and helpful, like a friend giving advice. Mention specific amounts and categories.",
  "total_income": 0.00,
  "total_expenses": 0.00,
  "top_categories": [
    {{"category": "Food", "amount": 0.00}},
    {{"category": "Shopping", "amount": 0.00}}
  ],
  "transactions": [
    {{"date": "2024-01-15", "description": "...", "amount": -25.00, "category": "Food"}}
  ]
}}

IMPORTANT: The "friendly_summary" is what the user will see in chat, so make it conversational and helpful. Example:
"You spent $342 this month, with most going to Food ($120) and Transportation ($85). You're doing well staying under budget! Maybe try meal prepping to save a bit more on dining out."

Return valid JSON only."""


def analyze_statement(file_content: bytes, filename: str) -> AssistantResponse:
    """
    Analyze a bank statement file.

    Args:
        file_content: Raw bytes of the uploaded file
        filename: Original filename (used to detect type)

    Returns:
        AssistantResponse with analysis text and optional visual payload
    """
    # Extract text from file
    statement_text = _extract_text(file_content, filename)

    if not statement_text:
        return AssistantResponse(
            text_message="I couldn't read that file. Please upload a PDF or CSV bank statement.",
            visual_payload=None
        )

    # Truncate if too long (LLM context limits)
    if len(statement_text) > 8000:
        statement_text = statement_text[:8000] + "\n...[truncated]..."

    # Send to LLM for analysis
    try:
        if not agent.is_available():
            return _fallback_response(statement_text)

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": USER_PROMPT_TEMPLATE.format(statement_text=statement_text)}
        ]

        response = agent.chat(messages)
        content = response.choices[0].message.content or ""

        # Try to parse JSON from response
        analysis = _parse_llm_json(content)

        if analysis:
            return _build_response(analysis)
        else:
            # LLM didn't return valid JSON, use the raw text
            return AssistantResponse(
                text_message=content[:500] if len(content) > 500 else content,
                visual_payload=None
            )

    except Exception as e:
        print(f"Statement analysis error: {e}")
        return _fallback_response(statement_text)


def _extract_text(file_content: bytes, filename: str) -> Optional[str]:
    """Extract text from PDF or CSV file."""
    filename_lower = filename.lower()

    if filename_lower.endswith(".csv"):
        return _parse_csv(file_content)
    elif filename_lower.endswith(".pdf"):
        return _parse_pdf(file_content)
    else:
        return None


def _parse_csv(file_content: bytes) -> str:
    """Parse CSV file into text representation."""
    try:
        text_content = file_content.decode("utf-8")
        reader = csv.reader(io.StringIO(text_content))
        rows = list(reader)

        # Format as readable text
        lines = []
        for row in rows[:100]:  # Limit rows
            lines.append(" | ".join(row))

        return "\n".join(lines)
    except Exception as e:
        print(f"CSV parse error: {e}")
        return ""


def _parse_pdf(file_content: bytes) -> str:
    """Parse PDF file into text. Requires pdfplumber."""
    try:
        import pdfplumber

        with pdfplumber.open(io.BytesIO(file_content)) as pdf:
            text_parts = []
            for page in pdf.pages[:10]:  # Limit pages
                text = page.extract_text()
                if text:
                    text_parts.append(text)

            return "\n\n".join(text_parts)
    except ImportError:
        print("pdfplumber not installed. Install with: pip install pdfplumber")
        return "[PDF parsing unavailable - install pdfplumber]"
    except Exception as e:
        print(f"PDF parse error: {e}")
        return ""


def _parse_llm_json(content: str) -> Optional[Dict[str, Any]]:
    """Try to extract JSON from LLM response."""
    # Try direct parse
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    # Try to find JSON block in response
    try:
        start = content.find("{")
        end = content.rfind("}") + 1
        if start != -1 and end > start:
            return json.loads(content[start:end])
    except json.JSONDecodeError:
        pass

    return None


def _build_response(analysis: Dict[str, Any]) -> AssistantResponse:
    """Build AssistantResponse from parsed analysis."""
    # Get friendly summary for text message
    friendly_summary = analysis.get("friendly_summary", "")

    if not friendly_summary:
        # Build a fallback summary from the data
        total_expenses = analysis.get("total_expenses", 0)
        top_categories = analysis.get("top_categories", [])

        if total_expenses and top_categories:
            top_cat = top_categories[0] if top_categories else {"category": "expenses", "amount": 0}
            friendly_summary = f"I analyzed your statement! You spent ${total_expenses:.2f} total, with {top_cat['category']} being your biggest category at ${top_cat['amount']:.2f}."
        else:
            friendly_summary = "I analyzed your statement. Check out the spending breakdown below!"

    # Build visual payload from transactions
    visual_payload = _build_visual_payload(analysis)

    return AssistantResponse(
        text_message=friendly_summary,
        visual_payload=visual_payload
    )


def _build_visual_payload(analysis: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Build a visual payload from the analysis."""
    # Try to use top_categories first (more reliable)
    top_categories = analysis.get("top_categories", [])
    total_income = analysis.get("total_income", 0)
    total_expenses = analysis.get("total_expenses", 0)

    if top_categories:
        nodes = []
        if total_income:
            nodes.append(SankeyNode(id="income", name="Income", value=float(total_income)))

        for cat in top_categories[:6]:
            cat_name = cat.get("category", "Other")
            cat_amount = cat.get("amount", 0)
            if isinstance(cat_amount, str):
                try:
                    cat_amount = float(cat_amount.replace("$", "").replace(",", ""))
                except ValueError:
                    cat_amount = 0
            if cat_amount > 0:
                nodes.append(SankeyNode(
                    id=cat_name.lower().replace(" ", "_"),
                    name=cat_name,
                    value=round(float(cat_amount), 2)
                ))

        if nodes:
            return VisualPayload.sankey_flow(nodes)

    # Fallback: parse from transactions
    transactions = analysis.get("transactions", [])
    if not transactions:
        return None

    category_totals: Dict[str, float] = {}
    for tx in transactions:
        amount = tx.get("amount", 0)
        category = tx.get("category", "Other")

        if isinstance(amount, str):
            try:
                amount = float(amount.replace("$", "").replace(",", ""))
            except ValueError:
                continue

        if amount < 0:
            category_totals[category] = category_totals.get(category, 0) + abs(amount)

    if not category_totals:
        return None

    nodes = []
    for category, total in sorted(category_totals.items(), key=lambda x: -x[1])[:6]:
        nodes.append(SankeyNode(
            id=category.lower().replace(" ", "_"),
            name=category,
            value=round(total, 2)
        ))

    return VisualPayload.sankey_flow(nodes)


def _fallback_response(statement_text: str) -> AssistantResponse:
    """Provide a basic response when LLM is unavailable."""
    # Count lines as proxy for transaction count
    line_count = len(statement_text.strip().split("\n"))

    return AssistantResponse(
        text_message=f"I received your statement ({line_count} lines). My AI backend is currently unavailable for detailed analysis. Please try again later.",
        visual_payload=None
    )
