"""
Recommendations generator for BudgetBuddy.
Uses a purpose-built LLM agent that calls financial tools to produce
structured JSON recommendations (not conversational prose).
"""

import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from services.llm_service import Agent
from services.tools import (
    _get_user_budget_plan,
    _get_plaid_transactions,
    _get_user_financial_summary,
    _get_user_spending_status,
)


RECOMMENDATIONS_SYSTEM_PROMPT = """You are BudgetBuddy's recommendation engine. Your job is to analyze a user's financial data and return structured, actionable recommendations.

You will receive the user's financial context (budget plan, transactions, financial summary, spending status) as pre-fetched data. Analyze it and return ONLY a JSON object with this exact schema:

{
  "recommendations": [
    {
      "category": "spending" | "saving" | "budgeting" | "income" | "habits",
      "title": "Short actionable title (max 60 chars)",
      "description": "1-2 sentence explanation with specific numbers from the data",
      "potentialSavings": 0.00,
      "priority": 1-5 (1=highest),
      "icon": "SF Symbol name"
    }
  ],
  "summary": "One sentence overall financial health summary"
}

RULES:
- Return 3-5 recommendations sorted by priority
- Use REAL numbers from the provided data — never make up amounts
- Each recommendation must be specific and actionable
- potentialSavings should be 0 if not applicable
- Use these SF Symbol icon names: "dollarsign.arrow.circlepath" (spending), "banknote" (saving), "chart.pie" (budgeting), "arrow.up.right" (income), "lightbulb" (habits), "exclamationmark.triangle" (warning)
- Return ONLY valid JSON, no markdown fences, no explanation text
"""

ACTION_PROMPTS = {
    "general": "Analyze all the user's financial data and provide general recommendations.",
    "budget_balance": "Focus on how the user's budget allocations compare to actual spending. Highlight categories that are over or under budget.",
    "spending_habits": "Focus on the user's spending patterns and habits. Identify trends, recurring expenses, and areas where small changes could save money.",
}

# Tool definitions for the recommendations agent (subset — no render_visual)
_RECO_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_budget_plan",
            "description": "Get the user's budget plan with category allocations.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_plaid_transactions",
            "description": "Get the user's recent bank transactions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "days": {"type": "integer", "description": "Number of days (default 30)"}
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_financial_summary",
            "description": "Get the user's financial summary (balances, net worth, safe-to-spend).",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_spending_status",
            "description": "Check if the user is on track with their budget.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
]


def _tool_executor(user_id: int):
    """Return a tool executor bound to the given user_id."""
    executors = {
        "get_budget_plan": lambda _: _get_user_budget_plan(user_id),
        "get_plaid_transactions": lambda args: _get_plaid_transactions(user_id, args.get("days", 30) if args else 30),
        "get_financial_summary": lambda _: _get_user_financial_summary(user_id),
        "get_spending_status": lambda _: _get_user_spending_status(user_id),
    }

    def execute(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if tool_name not in executors:
            raise ValueError(f"Unknown tool: {tool_name}")
        return executors[tool_name](arguments)

    return execute


def _parse_recommendations_json(raw: str) -> Optional[Dict[str, Any]]:
    """Try to extract valid JSON from the LLM response."""
    text = raw.strip()
    # Strip markdown fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)
    try:
        data = json.loads(text)
        if "recommendations" in data:
            return data
    except json.JSONDecodeError:
        pass
    return None


def _build_user_context(user_id: int) -> str:
    """Pre-fetch all financial data for the user so the agent has full context."""
    from services.orchestrator import _build_user_context as _orch_context
    return _orch_context(user_id) or "No financial data available for this user."


def _fallback_recommendations(user_id: int) -> Dict[str, Any]:
    """Fall back to the rules-based nudge generator when LLM is unavailable."""
    from services.nudge_generator import generate_nudges

    nudges = generate_nudges(user_id)
    recommendations = []
    for nudge in nudges:
        recommendations.append({
            "category": _nudge_type_to_category(nudge.get("type", "")),
            "title": nudge.get("title", "Financial Tip"),
            "description": nudge.get("message", ""),
            "potentialSavings": nudge.get("potentialSavings", 0),
            "priority": 3,
            "icon": "lightbulb",
        })

    # Get safe-to-spend from financial summary
    summary_data = _get_user_financial_summary(user_id)
    safe_to_spend = summary_data.get("safe_to_spend", 0)

    # Get spending status
    status_data = _get_user_spending_status(user_id)
    status = status_data.get("status", "unknown")

    return {
        "recommendations": recommendations,
        "safeToSpend": safe_to_spend,
        "status": status,
        "summary": "Based on your recent financial activity." if recommendations else "Connect your bank or create a budget plan to get personalized tips.",
    }


def _nudge_type_to_category(nudge_type: str) -> str:
    mapping = {
        "spending_reduction": "spending",
        "positive_reinforcement": "saving",
        "goal_reminder": "saving",
    }
    return mapping.get(nudge_type, "habits")


def generate_recommendations(user_id: int, action: str = "general") -> Dict[str, Any]:
    """
    Generate fresh recommendations using the LLM agent.
    Falls back to rules-based nudges if the LLM is unavailable.
    """
    # Pre-fetch financial context
    context = _build_user_context(user_id)
    action_prompt = ACTION_PROMPTS.get(action, ACTION_PROMPTS["general"])

    user_message = (
        f"{action_prompt}\n\n"
        f"[USER CONTEXT:\n{context}]"
    )

    try:
        agent = Agent(
            name="RecommendationsEngine",
            instructions=RECOMMENDATIONS_SYSTEM_PROMPT,
            tools=_RECO_TOOLS,
            model="claude-sonnet-4-20250514",
            tool_executor=_tool_executor(user_id),
            max_iterations=3,
        )

        if not agent.is_available():
            return _cache_and_return(user_id, _fallback_recommendations(user_id))

        result = agent.run(user_message)
        raw_content = result.get("content", "")

        parsed = _parse_recommendations_json(raw_content)
        if not parsed:
            return _cache_and_return(user_id, _fallback_recommendations(user_id))

        # Enrich with safe-to-spend and status from tool results
        tool_results = result.get("tool_results", [])
        safe_to_spend = 0
        status = "unknown"
        for tr in tool_results:
            if tr.get("tool") == "get_financial_summary":
                safe_to_spend = tr["result"].get("safe_to_spend", 0)
            if tr.get("tool") == "get_spending_status":
                status = tr["result"].get("status", "unknown")

        # If agent didn't call the tools, fetch directly
        if safe_to_spend == 0:
            summary_data = _get_user_financial_summary(user_id)
            safe_to_spend = summary_data.get("safe_to_spend", 0)
        if status == "unknown":
            status_data = _get_user_spending_status(user_id)
            status = status_data.get("status", "unknown")

        output = {
            "recommendations": parsed.get("recommendations", []),
            "safeToSpend": safe_to_spend,
            "status": status,
            "summary": parsed.get("summary", ""),
        }

        return _cache_and_return(user_id, output)

    except Exception as e:
        print(f"Recommendations generation error: {e}")
        return _cache_and_return(user_id, _fallback_recommendations(user_id))


def _cache_and_return(user_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
    """Cache recommendations in Datastore and return the response."""
    from db_models import upsert_cached_recommendations

    upsert_cached_recommendations(
        user_id,
        recommendations_json=json.dumps(data.get("recommendations", [])),
        safe_to_spend=data.get("safeToSpend", 0),
        status=data.get("status", "unknown"),
        summary=data.get("summary", ""),
    )

    data["cached"] = False
    data["generatedAt"] = datetime.utcnow().isoformat()
    return data


def get_cached_or_generate(user_id: int) -> Dict[str, Any]:
    """
    Return cached recommendations if fresh (<24h), otherwise generate new ones.
    """
    from db_models import get_cached_recommendations

    cached = get_cached_recommendations(user_id)
    if cached:
        updated_at = cached.get("updated_at")
        if updated_at:
            # Strip tzinfo for comparison (Datastore returns tz-aware datetimes)
            if hasattr(updated_at, "replace"):
                updated_at = updated_at.replace(tzinfo=None)
            if datetime.utcnow() - updated_at < timedelta(hours=24):
                try:
                    recommendations = json.loads(cached.get("recommendations_json", "[]"))
                except (json.JSONDecodeError, TypeError):
                    recommendations = []

                return {
                    "recommendations": recommendations,
                    "safeToSpend": cached.get("safe_to_spend", 0),
                    "status": cached.get("status", "unknown"),
                    "summary": cached.get("summary", ""),
                    "cached": True,
                    "generatedAt": updated_at.isoformat() if updated_at else None,
                }

    return generate_recommendations(user_id)
