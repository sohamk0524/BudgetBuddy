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
    _get_weekly_spending_status,
)


RECOMMENDATIONS_SYSTEM_PROMPT = """You are BudgetBuddy's hyper-local deal finder for college students. Your SOLE job is to find specific, real deals and discounts near the user's campus that save them money on things they ALREADY buy. You are a deal-finding engine, NOT a financial advisor.

TONE — write like an excited friend who just found an amazing deal:
- Conversational and direct — talk TO the user ("You're dropping $X at...", "Try this!")
- Slightly exclamative — use "!" naturally to celebrate easy saves
- Confident and encouraging, never preachy or corporate
- Example good tone: "Davis Co-op does 10% off Tuesdays with student ID — that's $4/week off your grocery run!"
- Example bad tone: "Consider reducing your grocery spending by shopping at more affordable stores."

═══════════════════════════════════════════════════════════
STRICT CONSTRAINT: THE "NO GENERIC ADVICE" RULE
═══════════════════════════════════════════════════════════
You must NEVER suggest behavioral changes or generic financial platitudes.
The user KEEPS their current lifestyle — your job is to find ways for them to pay LESS for it.

ABSOLUTELY FORBIDDEN (instant failure if you include any of these):
✗ "Cook at home instead of eating out"
✗ "Cancel subscriptions you don't use"
✗ "Start meal prepping"
✗ "Buy in bulk"
✗ "Use a budgeting app"
✗ "Stop buying coffee" / "Make coffee at home"
✗ "Set up automatic savings"
✗ "Track your spending"
✗ "Reduce impulse purchases"
✗ Any advice that tells the user to STOP doing something they enjoy

WHAT YOU MUST DO INSTEAD (pure deal-finding / arbitrage):
✓ Name a SPECIFIC local business with a SPECIFIC discount (e.g., "Philz does $1 off refills with your own cup")
✓ Cite exact student discount days or loyalty programs (e.g., "Show your Aggie Card at the Davis Co-op on Tuesdays for 10% off")
✓ Reference university-specific perks (e.g., "ASUCD Pantry has free staples for students")
✓ Provide exact steps to claim the deal (where to go, what to show, which day)
✓ Find a cheaper alternative for the SAME product/service at a nearby location

═══════════════════════════════════════════════════════════
MATHEMATICAL RIGOR
═══════════════════════════════════════════════════════════
All savings MUST pass this equation check:
  potentialSavings = (User's actual monthly spend on this) × (discount %)
  OR = (current price - deal price) × (monthly frequency from transaction data)

NEVER project $50 in savings on a category where the user only spends $30.
Calculate savings ONLY from frequency and amounts found in the actual transaction data.
If you cannot compute a realistic savings number, set potentialSavings to 0.

═══════════════════════════════════════════════════════════
FACTUAL ACCURACY / NO HALLUCINATION
═══════════════════════════════════════════════════════════
- Only recommend deals, businesses, and programs that you found via search_local_deals or that are well-known facts (e.g., ASUCD Pantry exists).
- If search_local_deals returns nothing useful for a category, SKIP that category. Quality > volume.
- Do NOT invent discount percentages, happy hours, or student deals that weren't in search results.
- When citing a deal, note the source if possible (e.g., "per their website" or "via Yelp").

═══════════════════════════════════════════════════════════
WORKFLOW — MANDATORY STEPS (complete in 2 tool rounds max)
═══════════════════════════════════════════════════════════
ROUND 1 — call ALL of these tools simultaneously in your first response:
  • get_plaid_transactions — get real spending data
  • get_weekly_spending_status — get remaining budget
  • search_local_deals — search for deals in the user's top spending category (infer from user context)

ROUND 2 — after reviewing Round 1 results:
  • Call search_local_deals 1-2 more times for other top categories if needed
  • Then produce your final JSON response

DO NOT use more than 2 tool-calling rounds. After Round 2, output your final JSON immediately.

OUTPUT FORMAT — return ONLY a JSON object, no markdown fences:
{
  "recommendations": [
    {
      "category": "spending" | "saving" | "budgeting" | "income" | "habits",
      "title": "Short actionable title (max 60 chars)",
      "description": "ONE short punchy sentence (max 18 words). Include the key number and the action. No compound sentences.",
      "potentialSavings": 0.00,
      "priority": 1-5 (1=highest),
      "icon": "SF Symbol name",

      "steps": ["Step 1 imperative sentence", "Step 2"],
      "spendingContext": "You spent $52 at Chipotle this month (4 visits)",
      "timeHorizon": "Every Tuesday",
      "link": "https://example.com/deal",
      "linkTitle": "View Menu"
    }
  ],
  "summary": "One sentence overall financial health summary referencing a key number"
}

RULES:
- Return exactly 3 recommendations sorted by priority (highest savings first)
- Each recommendation MUST reference a specific local business, deal, or student program
- CRITICAL: Each description must be ONE sentence, max 18 words. The title already provides context — the description just needs the hook.
- potentialSavings must be mathematically derived from actual transaction amounts and frequencies
- If you cannot find 3 verified deals, return fewer. NEVER pad with generic advice.
- Icon names: "dollarsign.arrow.circlepath" (spending), "banknote" (saving), "chart.pie" (budgeting), "arrow.up.right" (income), "lightbulb" (habits), "tag" (deals), "exclamationmark.triangle" (warning)
- Detail fields (steps, spendingContext, timeHorizon, link, linkTitle) are OPTIONAL. Include them ONLY for recommendations where the user can take a specific action or visit a specific place (e.g., restaurant alternatives, deals, subscription cancellations). OMIT all detail fields for status/tracking/encouragement recommendations (e.g., "you're on track").
- steps: 1-3 short imperative sentences. Focus on essential, nonredundant actions.
- spendingContext: ONE short phrase (max ~60 chars) referencing a real number from the user's transactions.
- timeHorizon: When/how often the deal applies (e.g., "Every Tuesday", "Weekdays 11am-2pm", "Ongoing"). Omit if unsure.
- link: When search_local_deals returns a URL for a specific restaurant or deal, include it. linkTitle should describe the destination (e.g., "View Menu", "See Deal"). Omit if no relevant URL.
- Return ONLY valid JSON, no markdown fences, no explanation text
"""

ACTION_PROMPTS = {
    "general": (
        "Analyze the user's transactions (both bank and voice-logged) and financial summary below.\n\n"
        "STEP 1: Call get_plaid_transactions to get real data.\n"
        "STEP 2: Identify the top 3 spending categories/merchants by dollar amount.\n"
        "STEP 3: For EACH top category, call search_local_deals with a targeted query like:\n"
        "  - 'student discount [cuisine] near [school]'\n"
        "  - '[category] deals [city near school]'\n"
        "  - 'loyalty program [store type] [city] student ID'\n"
        "STEP 4: Call get_weekly_spending_status.\n"
        "STEP 5: Build recommendations ONLY from verified search results.\n\n"
        "Remember: recommend specific local deals, NOT behavioral changes. "
        "The user keeps their lifestyle — you find them a cheaper way to live it."
    ),
    "budget_balance": (
        "Compare the user's budget allocations to their actual spending in each category.\n\n"
        "For categories where they're overspending:\n"
        "1. Calculate the exact overspend amount\n"
        "2. Call search_local_deals to find a specific cheaper alternative for that category near their school\n"
        "3. Show how switching to the deal would close the budget gap\n\n"
        "DO NOT tell the user to 'spend less' or 'cut back'. Instead, find a local deal or "
        "student discount that lets them keep buying the same things for less money."
    ),
    "spending_habits": (
        "Look at the user's transaction history (bank + voice-logged) for repeated merchants.\n\n"
        "For the top 3 most-visited merchants:\n"
        "1. Calculate total spent and visit frequency\n"
        "2. Call search_local_deals to find:\n"
        "   - Student discount days at that specific merchant\n"
        "   - Loyalty/rewards programs at that merchant\n"
        "   - A cheaper local competitor for the same product\n"
        "3. Compute exact savings: (current price - deal price) × monthly visits\n\n"
        "DO NOT suggest the user stop visiting these merchants. Find them a deal for the same thing."
    ),
    "food": (
        "Focus exclusively on the user's FOOD spending (restaurants, fast food, dining out).\n\n"
        "STEP 1: Call get_plaid_transactions and filter to food-related transactions.\n"
        "STEP 2: Identify top food merchants by spend.\n"
        "STEP 3: Call search_local_deals to find student food discounts, meal deals, and cheaper alternatives near their school.\n\n"
        "Only return food-related recommendations. Find specific local deals, not generic advice."
    ),
    "drink": (
        "Focus exclusively on the user's DRINK spending (coffee shops, cafes, boba, bars).\n\n"
        "STEP 1: Call get_plaid_transactions and filter to drink-related transactions.\n"
        "STEP 2: Identify top drink merchants by spend.\n"
        "STEP 3: Call search_local_deals to find student coffee discounts, loyalty programs, and cheaper alternatives near their school.\n\n"
        "Only return drink-related recommendations. Find specific local deals, not generic advice."
    ),
    "groceries": (
        "Focus exclusively on the user's GROCERY spending.\n\n"
        "STEP 1: Call get_plaid_transactions and filter to grocery transactions.\n"
        "STEP 2: Identify top grocery merchants by spend.\n"
        "STEP 3: Call search_local_deals to find student grocery discounts, bulk buying deals, and cheaper stores near their school.\n\n"
        "Only return grocery-related recommendations. Find specific local deals, not generic advice."
    ),
    "transportation": (
        "Focus exclusively on the user's TRANSPORTATION spending (rideshare, gas, parking, transit).\n\n"
        "STEP 1: Call get_plaid_transactions and filter to transportation transactions.\n"
        "STEP 2: Identify top transport expenses by spend.\n"
        "STEP 3: Call search_local_deals to find student transit passes, rideshare discounts, and cheaper alternatives near their school.\n\n"
        "Only return transportation-related recommendations. Find specific local deals, not generic advice."
    ),
    "entertainment": (
        "Focus exclusively on the user's ENTERTAINMENT spending (streaming, movies, events, gaming).\n\n"
        "STEP 1: Call get_plaid_transactions and filter to entertainment transactions.\n"
        "STEP 2: Identify top entertainment expenses by spend.\n"
        "STEP 3: Call search_local_deals to find student entertainment discounts, free campus events, and cheaper alternatives.\n\n"
        "Only return entertainment-related recommendations. Find specific local deals, not generic advice."
    ),
    "other": (
        "Focus on the user's miscellaneous spending (subscriptions, online shopping, recurring charges).\n\n"
        "STEP 1: Call get_plaid_transactions and look for recurring or miscellaneous charges.\n"
        "STEP 2: Identify subscriptions or repeated charges.\n"
        "STEP 3: Call search_local_deals to find student discounts for any subscriptions or cheaper alternatives.\n\n"
        "Only return recommendations for these miscellaneous expenses. Find specific deals, not generic advice."
    ),
}

SEARCH_PROMPT_TEMPLATE = (
    "The user is searching for deals related to: \"{query}\"\n\n"
    "STEP 1: Call get_plaid_transactions to understand the user's spending context.\n"
    "STEP 2: Call search_local_deals with the user's search query (and variations) to find relevant deals near their school.\n"
    "STEP 3: Call get_weekly_spending_status to understand their budget.\n"
    "STEP 4: If the first search didn't return great results, call search_local_deals again with a refined query.\n\n"
    "Return recommendations that match what the user searched for. "
    "Ground savings calculations in the user's actual transaction data where possible. "
    "If the search topic doesn't match their spending history, still find deals but set potentialSavings to 0."
)


def _get_action_prompt(action: str) -> str:
    """Return the prompt for a given action. Falls back to a dynamic prompt for custom categories."""
    if action in ACTION_PROMPTS:
        return ACTION_PROMPTS[action]

    # Dynamic prompt for custom categories using known keywords
    from services.classification_service import KNOWN_CATEGORY_KEYWORDS
    keywords = KNOWN_CATEGORY_KEYWORDS.get(action.lower(), [action])
    keyword_str = ", ".join(keywords[:6])
    display_name = action.capitalize()

    return (
        f"Focus exclusively on the user's {display_name.upper()} spending ({keyword_str}).\n\n"
        f"STEP 1: Call get_plaid_transactions and filter to {display_name.lower()}-related transactions.\n"
        f"STEP 2: Identify top {display_name.lower()} merchants by spend.\n"
        f"STEP 3: Call search_local_deals to find student {display_name.lower()} discounts, deals, and cheaper alternatives near their school.\n\n"
        f"Only return {display_name.lower()}-related recommendations. Find specific local deals, not generic advice."
    )


# Tool definitions for the recommendations agent (subset — no render_visual)
_RECO_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_plaid_transactions",
            "description": "Get the user's recent transactions from linked bank accounts AND voice-logged manual entries. Each transaction has a 'source' field ('plaid' or 'manual').",
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
            "name": "get_weekly_spending_status",
            "description": "Get the user's weekly spending limit, how much they've spent this week, remaining budget, and daily safe-to-spend amount. Always call this to ground recommendations in the user's actual remaining budget.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_local_deals",
            "description": "Fast web search for local deals and cheaper alternatives near the user's school. Returns raw results (title, snippet, URL) for you to interpret. Formulate queries from the user's actual merchants and categories (e.g., 'cheap Mexican food near UC Davis student deals').",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query derived from user's spending patterns"
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
    from services.tools import _search_local_deals

    executors = {
        "get_plaid_transactions": lambda args: _get_plaid_transactions(user_id, args.get("days", 30) if args else 30),
        "get_weekly_spending_status": lambda _: _get_weekly_spending_status(user_id),
        "search_local_deals": lambda args: _search_local_deals(user_id, args.get("query", "") if args else ""),
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
    if "```" in text:
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()

    # Try parsing the whole response (expected path with response_format=json_object)
    try:
        data = json.loads(text)
        if "recommendations" in data:
            return data
    except json.JSONDecodeError:
        pass

    # Fallback: extract JSON substring if LLM added preamble text
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace > first_brace:
        try:
            data = json.loads(text[first_brace:last_brace + 1])
            if "recommendations" in data:
                return data
        except json.JSONDecodeError:
            pass

    return None


def _get_user_recommendation_prefs(user_id: int):
    """Return (saved_tip_titles, disliked_tip_ids, seen_tip_ids) for the user."""
    from db_models import get_recommendation_prefs
    prefs = get_recommendation_prefs(user_id)
    if not prefs:
        return [], [], []
    try:
        saved_tips = json.loads(prefs.get("saved_tips_json", "[]"))
        saved_titles = [r.get("title", "") for r in saved_tips if r.get("title")]
    except (json.JSONDecodeError, TypeError):
        saved_titles = []
    try:
        disliked_ids = json.loads(prefs.get("disliked_tip_ids_json", "[]"))
    except (json.JSONDecodeError, TypeError):
        disliked_ids = []
    try:
        seen_raw = json.loads(prefs.get("seen_tip_ids_json", "[]"))
    except (json.JSONDecodeError, TypeError):
        seen_raw = []
    # Support both old format (string IDs) and new format (full objects)
    seen_ids = []
    for item in seen_raw:
        if isinstance(item, dict):
            seen_ids.append(item.get("category", "") + item.get("title", ""))
        elif isinstance(item, str):
            seen_ids.append(item)
    return saved_titles, disliked_ids, seen_ids


def _filter_hidden(recs: List[Dict], disliked_ids: List[str], seen_ids: List[str] = None) -> List[Dict]:
    """Remove recommendations that are disliked or already seen."""
    hidden = set(disliked_ids)
    if seen_ids:
        hidden.update(seen_ids)
    if not hidden:
        return recs
    return [r for r in recs if (r.get("category", "") + r.get("title", "")) not in hidden]


def _build_user_context(user_id: int) -> str:
    """Pre-fetch all financial data for the user so the agent has full context.

    Strips spending-strictness info since recommendations should not vary by strictness.
    Includes saved tip titles as a personalization signal.
    """
    import re
    from services.orchestrator import _build_user_context as _orch_context
    context = _orch_context(user_id) or "No financial data available for this user."
    context = re.sub(r",?\s*strictness=[^,\n)]*", "", context)

    saved_titles, disliked_ids, seen_ids = _get_user_recommendation_prefs(user_id)
    if saved_titles:
        context += f"\n\nSaved tips (user found these valuable — generate more like these): {', '.join(saved_titles)}"
    if disliked_ids:
        context += f"\n\nDisliked tip IDs (do NOT regenerate similar tips — user doesn't want these): {', '.join(disliked_ids[:20])}"
    if seen_ids:
        context += f"\n\nAlready seen tip IDs (user already knows about these deals — do NOT recommend the same ones, but similar deals from different businesses are OK): {', '.join(seen_ids[:20])}"

    return context


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


def generate_recommendations(user_id: int, action: str = "general", search_query: str = None) -> Dict[str, Any]:
    """
    Generate fresh recommendations using the LLM agent.

    Parameters:
        action: category or builtin action (default "general") — used when no search_query
        search_query: optional free-text deal search from the user — when provided, overrides
                      the action prompt so the agent searches for deals matching the query.
    Falls back to rules-based nudges if the LLM is unavailable.
    """
    # Pre-fetch financial context
    context = _build_user_context(user_id)

    # Search query and action are independent paths — search_query takes priority when present
    if search_query:
        action_prompt = SEARCH_PROMPT_TEMPLATE.format(query=search_query)
    else:
        action_prompt = _get_action_prompt(action)

    user_message = (
        f"{action_prompt}\n\n"
        f"[USER CONTEXT:\n{context}]"
    )

    try:
        agent = Agent(
            name="RecommendationsEngine",
            instructions=RECOMMENDATIONS_SYSTEM_PROMPT,
            tools=_RECO_TOOLS,
            model="claude-sonnet-4-5-20250929",
            tool_executor=_tool_executor(user_id),
            max_iterations=3,
            response_format={"type": "json_object"},
        )

        result = agent.run(user_message)
        raw_content = result.get("content", "")

        parsed = _parse_recommendations_json(raw_content)
        if not parsed:
            print(f"[RECO FALLBACK] user={user_id} reason=json_parse_failed raw={raw_content[:200]}")
            if search_query:
                return {"recommendations": [], "safeToSpend": 0, "status": "unknown", "summary": "No results found.", "cached": False}
            return _cache_and_return(user_id, _fallback_recommendations(user_id))

        # Compute safe-to-spend from weekly spending limit
        sts = _compute_safe_to_spend(user_id)
        safe_to_spend = sts["safe_to_spend"]
        status = sts["status"]

        recs = parsed.get("recommendations", [])[:5]
        if not search_query and action != "general":
            recs = [{**r, "spendingCategory": action} for r in recs]

        # Filter out disliked and seen tips
        _, disliked_ids, seen_ids = _get_user_recommendation_prefs(user_id)
        recs = _filter_hidden(recs, disliked_ids, seen_ids)

        output = {
            "recommendations": recs,
            "safeToSpend": safe_to_spend,
            "status": status,
            "summary": parsed.get("summary", ""),
        }

        # Search results are returned directly without polluting the recommendations cache
        if search_query:
            output["cached"] = False
            output["generatedAt"] = datetime.utcnow().isoformat()
            return output

        return _cache_and_return(user_id, output, action=action)

    except Exception as e:
        print(f"[RECO FALLBACK] user={user_id} reason=exception error={e}")
        if search_query:
            return {"recommendations": [], "safeToSpend": 0, "status": "unknown", "summary": "Search failed.", "cached": False}
        return _cache_and_return(user_id, _fallback_recommendations(user_id), action=action)


def _cache_and_return(user_id: int, data: Dict[str, Any], action: str = "general") -> Dict[str, Any]:
    """Cache recommendations in Datastore and return the response.

    For category-specific actions, new recs are merged into the existing cache so
    that general recommendations aren't wiped out by a single category generation.
    For 'general', the cache is fully replaced (intentional fresh start).
    """
    from db_models import upsert_cached_recommendations, get_cached_recommendations

    new_recs = data.get("recommendations", [])

    if action != "general":
        cached = get_cached_recommendations(user_id)
        if cached:
            try:
                existing_recs = json.loads(cached.get("recommendations_json", "[]"))
            except (json.JSONDecodeError, TypeError):
                existing_recs = []
            existing_ids = {
                (r.get("category", "") + r.get("title", "")) for r in existing_recs
            }
            added = [
                r for r in new_recs
                if (r.get("category", "") + r.get("title", "")) not in existing_ids
            ]
            new_recs = existing_recs + added

    upsert_cached_recommendations(
        user_id,
        recommendations_json=json.dumps(new_recs),
        safe_to_spend=data.get("safeToSpend", 0),
        status=data.get("status", "unknown"),
        summary=data.get("summary", ""),
    )

    data["recommendations"] = new_recs
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

                # Filter out disliked and seen tips from cached results
                _, disliked_ids, seen_ids = _get_user_recommendation_prefs(user_id)
                recommendations = _filter_hidden(recommendations, disliked_ids, seen_ids)

                return {
                    "recommendations": recommendations,
                    "safeToSpend": sts["safe_to_spend"],
                    "status": sts["status"],
                    "summary": cached.get("summary", ""),
                    "cached": True,
                    "generatedAt": updated_at.isoformat() if updated_at else None,
                }

    return generate_recommendations(user_id)
