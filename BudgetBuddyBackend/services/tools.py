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
            "description": "Get the user's recent transactions from their linked bank accounts via Plaid. Use this when the user asks about their recent spending, transactions, purchases, or where their money is going. This provides real transaction data from connected bank accounts.",
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
    }
    ,
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
        from db_models import get_active_plaid_items, get_accounts_for_item, get_transactions_since
        from datetime import datetime, timedelta

        plaid_items = get_active_plaid_items(user_id)
        if not plaid_items:
            return {
                "has_plaid": False,
                "message": "No bank accounts linked. The user should connect their bank via Plaid for transaction data."
            }

        account_ids = []
        accounts_info = []
        for item in plaid_items:
            for account in get_accounts_for_item(item.key.id):
                account_ids.append(account.key.id)
                accounts_info.append({
                    "name": account.get('name'),
                    "type": account.get('account_type'),
                    "balance": account.get('balance_current'),
                })

        if not account_ids:
            return {
                "has_plaid": True,
                "has_transactions": False,
                "message": "Bank accounts linked but no account data available.",
            }

        since_date = (datetime.now() - timedelta(days=days)).date()
        transactions = get_transactions_since(account_ids, since_date)
        # Sort and cap at 100
        transactions.sort(key=lambda t: t.get('date', ''), reverse=True)
        transactions = transactions[:100]

        if not transactions:
            return {
                "has_plaid": True,
                "has_transactions": False,
                "accounts": accounts_info,
                "message": f"No transactions found in the last {days} days.",
            }

        category_totals = {}
        transaction_list = []

        for txn in transactions:
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
            })

        sorted_categories = sorted(category_totals.items(), key=lambda x: x[1], reverse=True)
        total_spending = sum(category_totals.values())
        total_income = sum(-(txn.get('amount') or 0) for txn in transactions if (txn.get('amount') or 0) < 0)

        return {
            "has_plaid": True,
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
            "transaction_count": len(transactions),
            "summary": f"Found {len(transactions)} transactions in the last {days} days. Total spending: ${total_spending:.2f}, Total income: ${total_income:.2f}",
        }

    except Exception as e:
        return {"error": f"Failed to fetch Plaid transactions: {str(e)}", "has_plaid": False}



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
}


def get_visual_type_for_tool(tool_name: str) -> str:
    """Get the visual payload type associated with a tool."""
    return TOOL_TO_VISUAL_TYPE.get(tool_name)
