"""
Tools for BudgetBuddy AI agent.
Defines available tools with clear descriptions to guide when they should be used.
Tools fetch real user data when available, falling back to mock data otherwise.
"""

import json
from typing import Dict, Any, List, Callable, Optional
from services.data_mock import (
    get_budget_overview_data as get_mock_budget_overview,
    get_spending_status_data as get_mock_spending_status,
    get_savings_progress_data as get_mock_savings_progress
)


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
            "name": "get_budget_plan",
            "description": "Get the user's personalized budget plan including category allocations, recommendations, and spending limits. Use this when the user asks about their budget, spending plan, how to reduce spending, what they should spend on different categories, or wants advice on their finances.",
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
            "name": "get_spending_analysis",
            "description": "Get analysis of the user's actual spending from their bank statement, including spending by category and top expenses. Use this when the user asks about their actual spending habits, where their money is going, what they spent on, or wants to compare actual vs. planned spending.",
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
            "name": "get_budget_overview",
            "description": "Get a high-level budget breakdown showing income and expense categories. Use this when the user asks for a quick overview of their budget or where their money goes. Do NOT use for greetings.",
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
        from db_models import PlaidItem, PlaidAccount, Transaction
        from datetime import datetime, timedelta

        # Check if user has linked accounts
        plaid_items = PlaidItem.query.filter_by(user_id=user_id, status="active").all()

        if not plaid_items:
            return {
                "has_plaid": False,
                "message": "No bank accounts linked. The user should connect their bank via Plaid for transaction data."
            }

        # Get all account IDs
        account_ids = []
        accounts_info = []
        for item in plaid_items:
            for account in item.accounts:
                account_ids.append(account.id)
                accounts_info.append({
                    "name": account.name,
                    "type": account.account_type,
                    "balance": account.balance_current
                })

        if not account_ids:
            return {
                "has_plaid": True,
                "has_transactions": False,
                "message": "Bank accounts linked but no account data available."
            }

        # Get transactions from the last N days
        start_date = (datetime.now() - timedelta(days=days)).date()
        transactions = Transaction.query.filter(
            Transaction.plaid_account_id.in_(account_ids),
            Transaction.date >= start_date
        ).order_by(Transaction.date.desc()).limit(100).all()

        if not transactions:
            return {
                "has_plaid": True,
                "has_transactions": False,
                "accounts": accounts_info,
                "message": f"No transactions found in the last {days} days."
            }

        # Aggregate by category
        category_totals = {}
        transaction_list = []

        for txn in transactions:
            category = txn.category_primary or "Uncategorized"

            # Sum up spending by category (positive amounts are spending)
            if txn.amount > 0:
                category_totals[category] = category_totals.get(category, 0) + txn.amount

            transaction_list.append({
                "date": txn.date.isoformat() if txn.date else None,
                "name": txn.name,
                "merchant": txn.merchant_name,
                "amount": txn.amount,
                "category": category,
                "pending": txn.pending
            })

        # Sort categories by total
        sorted_categories = sorted(
            category_totals.items(),
            key=lambda x: x[1],
            reverse=True
        )

        total_spending = sum(category_totals.values())
        total_income = sum(-txn.amount for txn in transactions if txn.amount < 0)

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
            "summary": f"Found {len(transactions)} transactions in the last {days} days. Total spending: ${total_spending:.2f}, Total income: ${total_income:.2f}"
        }

    except Exception as e:
        return {"error": f"Failed to fetch Plaid transactions: {str(e)}", "has_plaid": False}


def _get_user_budget_plan(user_id: Optional[int]) -> Dict[str, Any]:
    """
    Fetch the user's most recent budget plan from the database.
    Returns the plan with all category allocations and recommendations.
    """
    if not user_id:
        return {"error": "No user ID provided", "has_plan": False}

    try:
        from db_models import BudgetPlan, User

        user = User.query.get(user_id)
        if not user:
            return {"error": "User not found", "has_plan": False}

        plan_record = BudgetPlan.query.filter_by(user_id=user_id).order_by(
            BudgetPlan.created_at.desc()
        ).first()

        if not plan_record:
            return {
                "has_plan": False,
                "message": "No budget plan found. The user should create a plan first."
            }

        plan_data = json.loads(plan_record.plan_json)

        # Extract key information for the AI to use
        categories = plan_data.get("categories", [])
        recommendations = plan_data.get("recommendations", [])
        warnings = plan_data.get("warnings", [])
        safe_to_spend = plan_data.get("safeToSpend", 0)

        return {
            "has_plan": True,
            "created_at": plan_record.created_at.isoformat() if plan_record.created_at else None,
            "month_year": plan_record.month_year,
            "safe_to_spend": safe_to_spend,
            "categories": categories,
            "recommendations": recommendations,
            "warnings": warnings,
            "summary": f"User has a budget plan with {len(categories)} categories and ${safe_to_spend:.2f} safe to spend."
        }

    except Exception as e:
        return {"error": f"Failed to fetch plan: {str(e)}", "has_plan": False}


def _get_user_spending_analysis(user_id: Optional[int]) -> Dict[str, Any]:
    """
    Fetch the user's spending analysis from their uploaded bank statement.
    Returns categorized spending and top expenses.
    """
    if not user_id:
        return {"error": "No user ID provided", "has_statement": False}

    try:
        from db_models import SavedStatement, User

        user = User.query.get(user_id)
        if not user:
            return {"error": "User not found", "has_statement": False}

        statement = SavedStatement.query.filter_by(user_id=user_id).first()

        if not statement:
            return {
                "has_statement": False,
                "message": "No bank statement uploaded. The user should upload a statement for spending analysis."
            }

        # Parse the LLM analysis
        analysis = {}
        if statement.llm_analysis:
            try:
                analysis = json.loads(statement.llm_analysis)
            except json.JSONDecodeError:
                pass

        # Get spending breakdown by category
        top_categories = analysis.get("top_categories", [])
        transactions = analysis.get("transactions", [])

        return {
            "has_statement": True,
            "total_income": statement.total_income,
            "total_expenses": statement.total_expenses,
            "ending_balance": statement.ending_balance,
            "statement_period": {
                "start": statement.statement_start_date.isoformat() if statement.statement_start_date else None,
                "end": statement.statement_end_date.isoformat() if statement.statement_end_date else None
            },
            "spending_by_category": top_categories,
            "transaction_count": len(transactions),
            "summary": f"From statement: ${statement.total_income:.2f} income, ${statement.total_expenses:.2f} expenses, ${statement.ending_balance:.2f} ending balance."
        }

    except Exception as e:
        return {"error": f"Failed to fetch spending analysis: {str(e)}", "has_statement": False}


def _get_user_financial_summary(user_id: Optional[int]) -> Dict[str, Any]:
    """
    Get comprehensive financial summary for the user.
    Combines statement data, profile data, and plan data.
    """
    if not user_id:
        return {"error": "No user ID provided"}

    try:
        from db_models import User, SavedStatement

        user = User.query.get(user_id)
        if not user:
            return {"error": "User not found"}

        result = {
            "has_profile": False,
            "has_statement": False,
            "monthly_income": 0,
            "net_worth": 0,
            "safe_to_spend": 0
        }

        # Get profile data
        if user.profile:
            result["has_profile"] = True
            result["monthly_income"] = user.profile.monthly_income
            result["fixed_expenses"] = user.profile.fixed_expenses
            result["financial_personality"] = user.profile.financial_personality
            result["primary_goal"] = user.profile.primary_goal

        # Get statement data
        statement = SavedStatement.query.filter_by(user_id=user_id).first()
        if statement:
            result["has_statement"] = True
            result["net_worth"] = statement.ending_balance
            result["total_income"] = statement.total_income
            result["total_expenses"] = statement.total_expenses
            # Safe to spend calculation (8% of net worth as per app.py)
            result["safe_to_spend"] = max(0, statement.ending_balance * 0.08)

        result["summary"] = f"Net worth: ${result['net_worth']:.2f}, Safe to spend: ${result['safe_to_spend']:.2f}"
        return result

    except Exception as e:
        return {"error": f"Failed to fetch financial summary: {str(e)}"}


def _get_user_budget_overview(user_id: Optional[int]) -> Dict[str, Any]:
    """
    Get budget overview - uses real plan data if available, otherwise mock data.
    """
    if user_id:
        plan_data = _get_user_budget_plan(user_id)
        if plan_data.get("has_plan"):
            # Transform plan data into overview format
            categories = plan_data.get("categories", [])
            total_budget = sum(cat.get("amount", 0) for cat in categories)

            return {
                "source": "user_plan",
                "total_budget": total_budget,
                "safe_to_spend": plan_data.get("safe_to_spend", 0),
                "categories": categories,
                "recommendations": plan_data.get("recommendations", [])
            }

    # Fall back to mock data
    return get_mock_budget_overview()


def _get_user_spending_status(user_id: Optional[int]) -> Dict[str, Any]:
    """
    Get spending status - uses real statement data if available.
    """
    if user_id:
        try:
            from db_models import SavedStatement, BudgetPlan
            import json

            statement = SavedStatement.query.filter_by(user_id=user_id).first()
            plan_record = BudgetPlan.query.filter_by(user_id=user_id).order_by(
                BudgetPlan.created_at.desc()
            ).first()

            if statement and plan_record:
                plan_data = json.loads(plan_record.plan_json)
                total_budget = sum(
                    cat.get("amount", 0)
                    for cat in plan_data.get("categories", [])
                )
                total_spent = statement.total_expenses

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
                    "source": "user_data",
                    "spent": total_spent,
                    "budget": total_budget,
                    "percent_used": round(percent_used, 1),
                    "status": status,
                    "statusMessage": message,
                    "remaining": max(0, total_budget - total_spent)
                }
        except Exception:
            pass

    # Fall back to mock data
    return get_mock_spending_status()


def _get_user_savings_progress(user_id: Optional[int]) -> Dict[str, Any]:
    """
    Get savings progress - uses profile data if available.
    """
    if user_id:
        try:
            from db_models import User

            user = User.query.get(user_id)
            if user and user.profile:
                profile = user.profile
                if profile.savings_goal_name and profile.savings_goal_target:
                    # We don't track current savings, so estimate from statement if available
                    from db_models import SavedStatement
                    statement = SavedStatement.query.filter_by(user_id=user_id).first()

                    current_savings = statement.ending_balance if statement else 0
                    target = profile.savings_goal_target

                    return {
                        "source": "user_data",
                        "goals": [{
                            "name": profile.savings_goal_name,
                            "target": target,
                            "current": current_savings,
                            "progress_percent": round((current_savings / target) * 100, 1) if target > 0 else 0
                        }],
                        "primary_goal": profile.primary_goal,
                        "summary": f"Saving for {profile.savings_goal_name}: ${current_savings:.2f} of ${target:.2f} target"
                    }
        except Exception:
            pass

    # Fall back to mock data
    return get_mock_savings_progress()


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
    "get_budget_plan": lambda _: _get_user_budget_plan(get_tool_context()),
    "get_spending_analysis": lambda _: _get_user_spending_analysis(get_tool_context()),
    "get_financial_summary": lambda _: _get_user_financial_summary(get_tool_context()),
    "get_budget_overview": lambda _: _get_user_budget_overview(get_tool_context()),
    "get_spending_status": lambda _: _get_user_spending_status(get_tool_context()),
    "get_savings_progress": lambda _: _get_user_savings_progress(get_tool_context()),
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


# Mapping from tool names to visual payload types
TOOL_TO_VISUAL_TYPE: Dict[str, Optional[str]] = {
    "get_plaid_transactions": "burndownChart",
    "get_budget_plan": "spendingPlan",
    "get_spending_analysis": "burndownChart",
    "get_financial_summary": "burndownChart",
    "get_budget_overview": "spendingPlan",  # or "sankeyFlow" for mock data
    "get_spending_status": "burndownChart",
    "get_savings_progress": None,
}


def get_visual_type_for_tool(tool_name: str) -> str:
    """Get the visual payload type associated with a tool."""
    return TOOL_TO_VISUAL_TYPE.get(tool_name)
