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
    _get_plaid_transactions,
    _get_user_financial_summary,
    _get_user_spending_status,
)


RECOMMENDATIONS_SYSTEM_PROMPT = """You are BudgetBuddy's recommendation engine for college students. Your job is to analyze a user's actual financial data and return 3 highly specific, actionable recommendations they can act on THIS WEEK.

TONE — write like an excited friend who's great with money:
- Conversational and direct — talk TO the user ("You're spending...", "Try this!")
- Slightly exclamative — use "!" naturally to celebrate wins or highlight easy saves
- Confident and encouraging, never preachy or corporate
- Example good tone: "That's $11 on Uber rides you could totally skip — free campus shuttles go everywhere!"
- Example bad tone: "You spent $11.73 on Uber rides this month. UC Davis offers free campus shuttles and bike rentals — using these instead could save you the full amount since most student destinations are campus-accessible."

WHAT MAKES A GOOD RECOMMENDATION:
- References specific merchants, amounts, and patterns from the user's real data
- Targets the highest-impact area first
- Gives a concrete next step, not vague advice

WHAT TO AVOID:
- Generic advice that doesn't reference the user's actual numbers
- Recommending app features, budgeting tools, or creating plans
- Recommendations that require major lifestyle changes
- Repeating what the user already knows without a specific alternative

OUTPUT FORMAT — return ONLY a JSON object, no markdown fences:
{
  "recommendations": [
    {
      "category": "spending" | "saving" | "budgeting" | "income" | "habits",
      "title": "Short actionable title (max 60 chars)",
      "description": "ONE short punchy sentence (max 18 words). Include the key number and the action. No compound sentences.",
      "potentialSavings": 0.00,
      "priority": 1-5 (1=highest),
      "icon": "SF Symbol name"
    }
  ],
  "summary": "One sentence overall financial health summary referencing a key number"
}

RULES:
- Return exactly 3 recommendations sorted by priority (highest impact first)
- CRITICAL: Each description must be ONE sentence, max 18 words. The title already provides context — the description just needs the hook.
- Use REAL numbers from the provided data — never make up amounts
- potentialSavings should be a realistic monthly estimate (0 if not applicable)
- Icon names: "dollarsign.arrow.circlepath" (spending), "banknote" (saving), "chart.pie" (budgeting), "arrow.up.right" (income), "lightbulb" (habits), "exclamationmark.triangle" (warning)
- Return ONLY valid JSON, no markdown fences, no explanation text
"""

ACTION_PROMPTS = {
    "general": (
        "Analyze the user's transactions and financial summary below. "
        "Identify the TOP spending categories by dollar amount, look for recurring charges "
        "(subscriptions, repeated merchants), and flag any unusual spikes. "
        "Prioritize recommendations by potential monthly savings — put the biggest wins first. "
        "If the user is a student, use the get_school_advice tool to find campus-specific deals "
        "or cheaper alternatives near their school."
    ),
    "budget_balance": (
        "Compare the user's budget allocations to their actual spending in each category. "
        "For categories where they're overspending, calculate by how much and suggest a specific "
        "swap or cutback. For categories where they're under budget, acknowledge it briefly. "
        "Focus on the 1-2 categories with the largest overspend gap."
    ),
    "spending_habits": (
        "Look at the user's transaction history for behavioral patterns: "
        "Which merchants appear most often? Are there small frequent purchases adding up "
        "(e.g., daily coffee, delivery fees)? Is spending higher on weekends? "
        "Any subscriptions they might have forgotten? "
        "Give concrete alternatives with estimated savings. "
        "If the user is a student, call get_school_advice to find student discounts or "
        "cheaper local options for their most-visited merchants."
    ),
}

# Tool definitions for the recommendations agent (subset — no render_visual)
_RECO_TOOLS = [
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
    {
        "type": "function",
        "function": {
            "name": "get_school_advice",
            "description": "Search the web for school-specific financial advice (student discounts, cheap food, campus resources). Use when the user is a student and recommendations could benefit from school-specific context.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The question to search for (e.g., 'student discounts', 'cheap food near campus')"
                    }
                },
                "required": ["query"],
            },
        },
    },
]


def _compute_safe_to_spend(user_id: int) -> Dict[str, Any]:
    """Compute safe-to-spend as Weekly Limit minus this week's transactions."""
    from db_models import (
        get_profile,
        get_active_plaid_items,
        get_accounts_for_item,
        get_transactions_for_accounts,
        get_manual_transactions,
    )

    profile = get_profile(user_id)
    weekly_limit = float(profile.get('weekly_spending_limit', 0)) if profile else 0

    if weekly_limit <= 0:
        return {"safe_to_spend": 0, "status": "unknown", "weekly_limit": 0, "spent": 0}

    # Monday of the current week
    today = datetime.utcnow().date()
    monday = today - timedelta(days=today.weekday())
    start_date = monday.isoformat()

    total_spent = 0.0

    # Plaid transactions for this week
    plaid_items = get_active_plaid_items(user_id)
    account_ids = []
    for item in plaid_items:
        for acc in get_accounts_for_item(item.key.id):
            account_ids.append(acc.key.id)
    if account_ids:
        txns, _ = get_transactions_for_accounts(account_ids, start_date=start_date, limit=10000)
        for txn in txns:
            amt = txn.get('amount') or 0
            if amt > 0:
                total_spent += amt

    # Manual transactions for this week
    manual_txns = get_manual_transactions(user_id, limit=500)
    for txn in manual_txns:
        txn_date = txn.get('date')
        if txn_date:
            if isinstance(txn_date, str):
                try:
                    txn_date = datetime.fromisoformat(txn_date).date()
                except ValueError:
                    continue
            elif hasattr(txn_date, 'date'):
                txn_date = txn_date.date()
            if txn_date >= monday:
                total_spent += float(txn.get('amount') or 0)

    safe_to_spend = round(weekly_limit - total_spent, 2)
    pct_remaining = safe_to_spend / weekly_limit if weekly_limit > 0 else 0

    if pct_remaining >= 0.2:
        status = "on_track"
    elif pct_remaining > 0:
        status = "caution"
    else:
        status = "over_budget"

    return {
        "safe_to_spend": safe_to_spend,
        "status": status,
        "weekly_limit": weekly_limit,
        "spent": round(total_spent, 2),
    }


def _tool_executor(user_id: int):
    """Return a tool executor bound to the given user_id."""
    from services.tools import _get_school_advice

    executors = {
        "get_plaid_transactions": lambda args: _get_plaid_transactions(user_id, args.get("days", 30) if args else 30),
        "get_financial_summary": lambda _: _get_user_financial_summary(user_id),
        "get_spending_status": lambda _: _get_user_spending_status(user_id),
        "get_school_advice": lambda args: _get_school_advice(user_id, args.get("query", "") if args else ""),
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
    from services.recommendation_templates import run_all_templates

    nudges = generate_nudges(user_id)
    nudge_recs = []
    for nudge in nudges:
        nudge_recs.append({
            "category": _nudge_type_to_category(nudge.get("type", "")),
            "title": nudge.get("title", "Financial Tip"),
            "description": nudge.get("message", ""),
            "potentialSavings": nudge.get("potentialSavings", 0),
            "priority": 3,
            "icon": "lightbulb",
        })

    # Templates first, then nudges, max 5 total
    template_recs = run_all_templates(user_id)
    recommendations = (template_recs + nudge_recs)[:5]

    # Compute safe-to-spend from weekly spending limit
    sts = _compute_safe_to_spend(user_id)
    safe_to_spend = sts["safe_to_spend"]
    status = sts["status"]

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

        # Compute safe-to-spend from weekly spending limit
        sts = _compute_safe_to_spend(user_id)
        safe_to_spend = sts["safe_to_spend"]
        status = sts["status"]

        # Merge template-based recommendations (first) with LLM recommendations
        from services.recommendation_templates import run_all_templates

        template_recs = run_all_templates(user_id)
        llm_recs = parsed.get("recommendations", [])
        combined = (template_recs + llm_recs)[:5]

        output = {
            "recommendations": combined,
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

                # Always recompute safe-to-spend from weekly limit
                sts = _compute_safe_to_spend(user_id)

                return {
                    "recommendations": recommendations,
                    "safeToSpend": sts["safe_to_spend"],
                    "status": sts["status"],
                    "summary": cached.get("summary", ""),
                    "cached": True,
                    "generatedAt": updated_at.isoformat() if updated_at else None,
                }

    return generate_recommendations(user_id)
