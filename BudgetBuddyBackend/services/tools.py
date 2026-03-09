"""
Tools for BudgetBuddy AI agent.
Defines available tools with clear descriptions to guide when they should be used.
Tools fetch real user data when available, falling back to mock data otherwise.
"""

import json
from typing import Dict, Any, List, Callable, Optional


# Tool definitions with explicit usage guidance
TOOL_DEFINITIONS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_plaid_transactions",
            "description": "Get the user's recent transactions from linked bank accounts (Plaid) AND voice-logged manual transactions. Use this when the user asks about their recent spending, transactions, purchases, or where their money is going. Each transaction includes a 'source' field ('plaid' or 'manual').",
            "parameters": {
                "type": "object",
                "properties": {
                    "days": {
                        "type": "integer",
                        "description": "Number of days of transactions to fetch (default 30)"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_financial_summary",
            "description": "Get the user's overall financial summary including net worth, safe-to-spend amount, and account balances. Use this when the user asks about their balance, how much money they have, their financial health, or safe spending amount.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_spending_status",
            "description": "Check if the user is on track with their budget and spending pace. Use when the user asks about affordability (can I afford X?), spending pace, budget status, or if they're overspending.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_savings_progress",
            "description": "Get the user's progress toward their savings goals. Use when the user asks about savings, saving goals, or their progress toward financial goals.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_weekly_spending_status",
            "description": "Get the user's weekly spending limit, how much they've spent this week (from both bank and voice-logged transactions), how much is left for the rest of the week, and the daily safe-to-spend amount for today. Use when the user asks how much they can spend today, or when making recommendations that reference their remaining budget.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_school_advice",
            "description": "Search the web for school-specific financial advice using the student's university context. Use this when the user asks about student discounts, cheap food near campus, campus resources, scholarships, or any question that benefits from knowing their school. Requires a query describing what the user wants to know.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The user's question to search for school-specific advice (e.g., 'cheap coffee near campus', 'student discounts')"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_local_deals",
            "description": "Fast web search for local deals, discounts, and cheaper alternatives near the user's school. Returns raw search results (title, snippet, URL) for the agent to interpret. Use this to find specific deals based on the user's actual spending patterns (e.g., 'cheap burritos near UC Davis student discount', 'affordable grocery stores Davis CA').",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query for local deals (e.g., 'cheap Mexican food near UC Davis student deals')"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "render_visual",
            "description": "Render a visual chart or diagram for the user. Only call this when you have REAL user data to display and a visualization would genuinely help. Do NOT call this if the user has no data, no plan, or no linked accounts. Available visual types: 'spending_plan' (shows budget categories and safe-to-spend), 'burndown_chart' (shows spending pace vs budget), 'sankey_flow' (shows money flow between categories).",
            "parameters": {
                "type": "object",
                "properties": {
                    "visual_type": {
                        "type": "string",
                        "enum": ["spending_plan", "burndown_chart", "sankey_flow"],
                        "description": "The type of visualization to render"
                    },
                    "data": {
                        "type": "object",
                        "description": "The data for the visualization. For spending_plan: {safe_to_spend, categories}. For burndown_chart: {spent, budget, ideal_pace}. For sankey_flow: {nodes: [{id, name, value}]}."
                    }
                },
                "required": ["visual_type", "data"]
            }
        }
    }
]


# ============================================
# USER DATA FETCHERS (Real data from database)
# ============================================

def _get_plaid_transactions(user_id: Optional[int], days: int = 30) -> Dict[str, Any]:
    """
    Fetch recent transactions from Plaid-linked bank accounts.
    Returns categorized transactions for AI context.
    """
    if not user_id:
        return {"error": "No user ID provided", "has_plaid": False}

    try:
        from db_models import get_active_plaid_items, get_accounts_for_item, get_transactions_since, get_manual_transactions
        from datetime import datetime, timedelta

        plaid_items = get_active_plaid_items(user_id)
        has_plaid = bool(plaid_items)

        account_ids = []
        accounts_info = []
        if plaid_items:
            for item in plaid_items:
                for account in get_accounts_for_item(item.key.id):
                    account_ids.append(account.key.id)
                    accounts_info.append({
                        "name": account.get('name'),
                        "type": account.get('account_type'),
                        "balance": account.get('balance_current'),
                    })

        since_date = (datetime.now() - timedelta(days=days)).date()

        # Fetch Plaid transactions
        plaid_txns = []
        if account_ids:
            plaid_txns = get_transactions_since(account_ids, since_date)

        # Fetch manual (voice-logged) transactions
        manual_txns_raw = get_manual_transactions(user_id, limit=500)
        print(f"[get_plaid_transactions] user={user_id} plaid_txns={len(plaid_txns)} manual_txns_raw={len(manual_txns_raw)}")
        manual_txns = []
        for mt in manual_txns_raw:
            mt_date = mt.get('date')
            if not mt_date:
                # No date — include it anyway (recent voice log)
                manual_txns.append(mt)
                continue
            # Normalize to a date object for comparison
            if isinstance(mt_date, str):
                try:
                    mt_date_obj = datetime.fromisoformat(mt_date).date()
                except ValueError:
                    mt_date_obj = None
            elif hasattr(mt_date, 'date'):
                # datetime object (possibly tz-aware from Datastore)
                mt_date_obj = mt_date.date()
            elif hasattr(mt_date, 'isoformat'):
                # already a date object
                mt_date_obj = mt_date
            else:
                mt_date_obj = None
            if mt_date_obj is None or mt_date_obj >= since_date:
                manual_txns.append(mt)
        print(f"[get_plaid_transactions] after date filter: manual_txns={len(manual_txns)} since_date={since_date}")

        if not plaid_txns and not manual_txns:
            return {
                "has_plaid": has_plaid,
                "has_transactions": False,
                "accounts": accounts_info,
                "message": f"No transactions found in the last {days} days." if has_plaid else "No bank accounts linked and no manual transactions found.",
            }

        # Build unified transaction list
        category_totals = {}
        transaction_list = []

        for txn in plaid_txns:
            category = txn.get('category_primary') or "Uncategorized"
            amount = txn.get('amount') or 0
            if amount > 0:
                category_totals[category] = category_totals.get(category, 0) + amount
            transaction_list.append({
                "date": txn.get('date'),
                "name": txn.get('name'),
                "merchant": txn.get('merchant_name'),
                "amount": amount,
                "category": category,
                "pending": txn.get('pending'),
                "source": "plaid",
            })

        for mt in manual_txns:
            category = mt.get('category') or "Uncategorized"
            amount = float(mt.get('amount') or 0)
            if amount > 0:
                category_totals[category] = category_totals.get(category, 0) + amount
            mt_date = mt.get('date')
            if hasattr(mt_date, 'isoformat'):
                mt_date = mt_date.isoformat()
            transaction_list.append({
                "date": mt_date,
                "name": mt.get('store') or mt.get('notes') or "Manual entry",
                "merchant": mt.get('store'),
                "amount": amount,
                "category": category,
                "pending": False,
                "source": "manual",
            })

        # Sort combined list by date descending, cap at 100
        transaction_list.sort(key=lambda t: t.get('date') or '', reverse=True)
        transaction_list = transaction_list[:100]

        sorted_categories = sorted(category_totals.items(), key=lambda x: x[1], reverse=True)
        total_spending = sum(category_totals.values())
        all_amounts = [t.get('amount', 0) for t in plaid_txns] + [float(mt.get('amount') or 0) for mt in manual_txns]
        total_income = sum(-a for a in all_amounts if a < 0)

        total_count = len(plaid_txns) + len(manual_txns)
        return {
            "has_plaid": has_plaid,
            "has_transactions": True,
            "period_days": days,
            "accounts": accounts_info,
            "total_spending": round(total_spending, 2),
            "total_income": round(total_income, 2),
            "spending_by_category": [
                {"category": cat, "amount": round(amt, 2)}
                for cat, amt in sorted_categories[:10]
            ],
            "recent_transactions": transaction_list[:20],
            "transaction_count": total_count,
            "plaid_count": len(plaid_txns),
            "manual_count": len(manual_txns),
            "summary": f"Found {total_count} transactions ({len(plaid_txns)} bank, {len(manual_txns)} voice-logged) in the last {days} days. Total spending: ${total_spending:.2f}, Total income: ${total_income:.2f}",
        }

    except Exception as e:
        return {"error": f"Failed to fetch transactions: {str(e)}", "has_plaid": False}



def _get_user_financial_summary(user_id: Optional[int]) -> Dict[str, Any]:
    """
    Get comprehensive financial summary for the user.
    Combines statement data, profile data, and plan data.
    """
    if not user_id:
        return {"error": "No user ID provided"}

    try:
        from db_models import get_user, get_profile, get_statement

        user = get_user(user_id)
        if not user:
            return {"error": "User not found"}

        result: Dict[str, Any] = {
            "has_profile": False,
            "has_statement": False,
            "net_worth": 0,
            "safe_to_spend": 0,
        }

        profile = get_profile(user_id)
        if profile:
            result["has_profile"] = True
            result["is_student"] = profile.get('is_student')
            result["budgeting_goal"] = profile.get('budgeting_goal')
            result["strictness_level"] = profile.get('strictness_level')

        statement = get_statement(user_id)
        if statement:
            ending_balance = statement.get('ending_balance') or 0
            result["has_statement"] = True
            result["net_worth"] = ending_balance
            result["total_income"] = statement.get('total_income') or 0
            result["total_expenses"] = statement.get('total_expenses') or 0
            result["safe_to_spend"] = max(0, ending_balance * 0.08)

        result["summary"] = f"Net worth: ${result['net_worth']:.2f}, Safe to spend: ${result['safe_to_spend']:.2f}"
        return result

    except Exception as e:
        return {"error": f"Failed to fetch financial summary: {str(e)}"}



def _get_user_spending_status(user_id: Optional[int]) -> Dict[str, Any]:
    """
    Get spending status - uses real statement and plan data.
    """
    if not user_id:
        return {"has_status": False, "message": "No user ID provided."}

    try:
        from db_models import get_statement, get_latest_plan

        statement = get_statement(user_id)
        plan_record = get_latest_plan(user_id)

        if not plan_record and not statement:
            return {
                "has_status": False,
                "message": "No budget plan or bank statement found. The user needs to create a plan and upload a statement first.",
            }
        if not plan_record:
            return {
                "has_status": False,
                "message": "No budget plan found. The user should create a plan first to track spending status.",
            }
        if not statement:
            return {
                "has_status": False,
                "message": "No bank statement found. The user should upload a statement to track spending status.",
            }

        plan_data = json.loads(plan_record['plan_json'])
        total_budget = sum(
            cat.get("amount", 0)
            for cat in plan_data.get("categories", [])
        )
        total_spent = statement.get('total_expenses') or 0

        # Calculate status
        if total_budget > 0:
            percent_used = (total_spent / total_budget) * 100
            if percent_used < 80:
                status = "on_track"
                message = "You're doing well! Spending is under control."
            elif percent_used < 100:
                status = "caution"
                message = "Be careful - you're approaching your budget limit."
            else:
                status = "over_budget"
                message = "You've exceeded your planned budget."
        else:
            percent_used = 0
            status = "unknown"
            message = "No budget set to compare against."

        return {
            "has_status": True,
            "source": "user_data",
            "spent": total_spent,
            "budget": total_budget,
            "percent_used": round(percent_used, 1),
            "status": status,
            "statusMessage": message,
            "remaining": max(0, total_budget - total_spent)
        }
    except Exception as e:
        return {"has_status": False, "message": f"Error fetching spending status: {str(e)}"}


def _get_user_savings_progress(user_id: Optional[int]) -> Dict[str, Any]:
    """
    Get savings progress - uses profile data if available.
    """
    if not user_id:
        return {"has_savings_data": False, "message": "No user ID provided."}

    try:
        from db_models import get_user, get_profile, get_statement

        user = get_user(user_id)
        if not user:
            return {
                "has_savings_data": False,
                "message": "No financial profile found. The user should complete onboarding first.",
            }

        profile = get_profile(user_id)
        if not profile:
            return {
                "has_savings_data": False,
                "message": "No financial profile found. The user should complete onboarding first.",
            }

        goal_name = profile.get('savings_goal_name')
        goal_target = profile.get('savings_goal_target') or 0
        if not goal_name or not goal_target:
            return {
                "has_savings_data": False,
                "message": "No savings goals set up. The user should set a savings goal in their profile.",
            }

        statement = get_statement(user_id)
        current_savings = (statement.get('ending_balance') or 0) if statement else 0

        return {
            "has_savings_data": True,
            "source": "user_data",
            "goals": [{
                "name": goal_name,
                "target": goal_target,
                "current": current_savings,
                "progress_percent": round((current_savings / goal_target) * 100, 1) if goal_target > 0 else 0,
            }],
            "budgeting_goal": profile.get('budgeting_goal'),
            "summary": f"Saving for {goal_name}: ${current_savings:.2f} of ${goal_target:.2f} target",
        }
    except Exception as e:
        return {"has_savings_data": False, "message": f"Error fetching savings progress: {str(e)}"}


def _get_weekly_spending_status(user_id: Optional[int]) -> Dict[str, Any]:
    """
    Get weekly spending limit, amount spent this week, remaining budget,
    and daily safe-to-spend for the rest of the week.
    """
    if not user_id:
        return {"error": "No user ID provided"}

    try:
        from db_models import (
            get_profile,
            get_active_plaid_items,
            get_accounts_for_item,
            get_transactions_for_accounts,
            get_manual_transactions,
        )
        from datetime import datetime, timedelta

        profile = get_profile(user_id)
        weekly_limit = float(profile.get('weekly_spending_limit', 0)) if profile else 0

        if weekly_limit <= 0:
            return {
                "has_weekly_limit": False,
                "message": "No weekly spending limit set. The user should set one in their profile.",
            }

        today = datetime.utcnow().date()
        monday = today - timedelta(days=today.weekday())
        start_date = monday.isoformat()
        days_left = max(1, 7 - today.weekday())  # days remaining including today

        total_spent = 0.0

        # Plaid transactions this week
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

        # Manual transactions this week
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

        remaining = round(weekly_limit - total_spent, 2)
        daily_safe = round(remaining / days_left, 2) if remaining > 0 else 0

        day_name = today.strftime('%A')

        return {
            "has_weekly_limit": True,
            "weekly_limit": weekly_limit,
            "spent_this_week": round(total_spent, 2),
            "remaining_this_week": remaining,
            "days_left_in_week": days_left,
            "daily_safe_to_spend": daily_safe,
            "today": day_name,
            "summary": f"Weekly limit: ${weekly_limit:.2f}. Spent so far: ${total_spent:.2f}. "
                       f"Remaining: ${remaining:.2f} over {days_left} days = ${daily_safe:.2f}/day safe to spend.",
        }

    except Exception as e:
        return {"error": f"Failed to get weekly spending status: {str(e)}"}


def _get_school_advice(user_id: Optional[int], query: str) -> Dict[str, Any]:
    """
    Get school-specific financial advice via web search (Tavily RAG).
    Looks up the user's school from their profile and searches for relevant info.
    """
    if not user_id:
        return {"error": "No user ID provided"}
    if not query:
        return {"error": "No query provided"}

    try:
        from db_models import get_profile
        from services.school_rag import get_school_advice

        profile = get_profile(user_id)
        school_slug = profile.get("school") if profile else None

        if not school_slug:
            return {
                "error": "No school found in user profile. The user should complete onboarding with their school."
            }

        result = get_school_advice(query, school_slug)
        return result

    except Exception as e:
        return {"error": f"Failed to get school advice: {str(e)}"}


# In-memory Tavily result cache: key → (timestamp, result)
_tavily_cache: Dict[str, tuple] = {}
_TAVILY_CACHE_TTL = 60 * 60 * 24  # 24 hours


def _search_local_deals(user_id: Optional[int], query: str) -> Dict[str, Any]:
    """
    Lightweight local deal search via Tavily. No LLM rewrite or synthesis —
    returns raw results for the agent to interpret.
    Tavily results are cached in-memory for 24h keyed by normalized query.
    """
    import time

    if not user_id:
        return {"error": "No user ID provided"}
    if not query:
        return {"error": "No query provided"}

    try:
        import os
        from db_models import get_profile
        from services.school_rag import SCHOOL_DISPLAY_NAMES

        profile = get_profile(user_id)
        school_slug = profile.get("school") if profile else None

        if not school_slug:
            return {"error": "No school found in user profile."}

        school_display = SCHOOL_DISPLAY_NAMES.get(
            school_slug, school_slug.replace("_", " ").title()
        )

        # Append school context if not already in query
        if school_display.lower() not in query.lower():
            query = f"{query} near {school_display}"

        # Local curated deals (always available, no API key needed)
        from services.local_deals import match_deals
        query_keywords = [w.lower() for w in query.split() if len(w) > 2]
        local_matches = match_deals(school_slug, query_keywords)
        local_results = [
            {
                "title": d["name"],
                "snippet": f"{d.get('deal', '')} — {d.get('schedule', '')}".strip(" —"),
                "url": d.get("url", ""),
            }
            for d in local_matches
        ]

        # Web search via Tavily (may fail if key not set)
        tavily_results = []
        tavily_answer = ""
        tavily_key = os.environ.get("TAVILY_API_KEY")
        if tavily_key:
            # Check cache first (normalized: lowercase + stripped)
            cache_key = query.strip().lower()
            now = time.time()
            cached = _tavily_cache.get(cache_key)
            if cached and (now - cached[0]) < _TAVILY_CACHE_TTL:
                print(f"[search_local_deals] Tavily cache HIT for: {cache_key[:60]}")
                tavily_answer = cached[1].get("answer", "")
                tavily_results = cached[1].get("results", [])
            else:
                try:
                    from tavily import TavilyClient
                    client = TavilyClient(api_key=tavily_key)
                    search_results = client.search(
                        query=query,
                        search_depth="basic",
                        max_results=5,
                        include_answer=True,
                    )
                    tavily_answer = search_results.get("answer", "")
                    for r in search_results.get("results", []):
                        tavily_results.append({
                            "title": r.get("title", ""),
                            "snippet": r.get("content", ""),
                            "url": r.get("url", ""),
                        })
                    # Cache the result
                    _tavily_cache[cache_key] = (now, {
                        "answer": tavily_answer,
                        "results": tavily_results,
                    })
                    print(f"[search_local_deals] Tavily cache MISS, stored: {cache_key[:60]}")
                except Exception as e:
                    print(f"[search_local_deals] Tavily search failed (non-fatal): {e}")

        # Local deals first, then web results
        results = local_results + tavily_results

        if not results and not tavily_answer:
            return {"error": "No deals found and TAVILY_API_KEY not configured" if not tavily_key else "No results found"}

        return {
            "school": school_display,
            "query": query,
            "answer": tavily_answer,
            "results": results,
        }

    except Exception as e:
        return {"error": f"Deal search failed: {str(e)}"}


def _render_visual(visual_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Package visual data for the frontend.
    The orchestrator reads this from tool_results to build the visual payload.
    """
    return {
        "rendered": True,
        "visual_type": visual_type,
        "data": data
    }


# ============================================
# TOOL EXECUTOR
# ============================================

# Store current user_id for tool execution context
_current_user_id: Optional[int] = None


def set_tool_context(user_id: Optional[int]):
    """Set the user context for tool execution."""
    global _current_user_id
    _current_user_id = user_id


def get_tool_context() -> Optional[int]:
    """Get the current user context."""
    return _current_user_id


# Tool executor registry - now uses user context
TOOL_EXECUTORS: Dict[str, Callable] = {
    "get_plaid_transactions": lambda args: _get_plaid_transactions(get_tool_context(), args.get("days", 30) if args else 30),
    "get_financial_summary": lambda _: _get_user_financial_summary(get_tool_context()),
    "get_spending_status": lambda _: _get_user_spending_status(get_tool_context()),
    "get_savings_progress": lambda _: _get_user_savings_progress(get_tool_context()),
    "render_visual": lambda args: _render_visual(args.get("visual_type"), args.get("data", {})),
    "get_school_advice": lambda args: _get_school_advice(get_tool_context(), args.get("query", "")),
    "search_local_deals": lambda args: _search_local_deals(get_tool_context(), args.get("query", "")),
    "get_weekly_spending_status": lambda _: _get_weekly_spending_status(get_tool_context()),
}


def execute_tool(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute a tool by name with the given arguments.
    Uses the current user context set via set_tool_context().

    Args:
        tool_name: Name of the tool to execute
        arguments: Arguments to pass to the tool

    Returns:
        Tool execution result as a dictionary

    Raises:
        ValueError: If tool name is not recognized
    """
    if tool_name not in TOOL_EXECUTORS:
        raise ValueError(f"Unknown tool: {tool_name}")

    executor = TOOL_EXECUTORS[tool_name]
    return executor(arguments)


def get_tool_definitions() -> List[Dict[str, Any]]:
    """Get the list of tool definitions for the LLM."""
    return TOOL_DEFINITIONS


def get_tools() -> List[Dict[str, Any]]:
    """Get tool definitions for agent initialization."""
    return TOOL_DEFINITIONS


# Mapping from tool names to visual payload types
TOOL_TO_VISUAL_TYPE: Dict[str, Optional[str]] = {
    "get_plaid_transactions": "burndownChart",
    "get_financial_summary": "burndownChart",
    "get_spending_status": "burndownChart",
    "get_savings_progress": None,
    "get_school_advice": None,
    "search_local_deals": None,
    "get_weekly_spending_status": None,
}


def get_visual_type_for_tool(tool_name: str) -> str:
    """Get the visual payload type associated with a tool."""
    return TOOL_TO_VISUAL_TYPE.get(tool_name)
