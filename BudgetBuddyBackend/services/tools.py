"""
Tools for BudgetBuddy AI agent.
Defines available tools with clear descriptions to guide when they should be used.
"""

from typing import Dict, Any, List, Callable
from services.data_mock import (
    get_budget_overview_data,
    get_spending_status_data,
    get_account_balance_data,
    get_savings_progress_data
)


def check_user_setup_status(user_id: int) -> Dict[str, Any]:
    """
    Check if the user has completed their financial setup.
    Returns status of profile, budget plan, and statements.
    """
    try:
        from db_models import User, BudgetPlan, SavedStatement, FinancialProfile

        has_profile = False
        has_plan = False
        has_statement = False
        profile_complete = False

        # Check profile
        profile = FinancialProfile.query.filter_by(user_id=user_id).first()
        if profile:
            has_profile = True
            profile_complete = profile.monthly_income is not None and profile.monthly_income > 0

        # Check budget plan
        plan = BudgetPlan.query.filter_by(user_id=user_id).first()
        has_plan = plan is not None

        # Check statements
        statement = SavedStatement.query.filter_by(user_id=user_id).first()
        has_statement = statement is not None

        # Determine what's missing and provide guidance
        missing_items = []
        next_step = None

        if not has_profile or not profile_complete:
            missing_items.append("financial profile")
            next_step = "complete_profile"
        elif not has_plan:
            missing_items.append("budget plan")
            next_step = "create_budget_plan"

        return {
            "has_profile": has_profile,
            "profile_complete": profile_complete,
            "has_budget_plan": has_plan,
            "has_statement": has_statement,
            "is_fully_setup": has_profile and profile_complete and has_plan,
            "missing_items": missing_items,
            "next_step": next_step,
            "message": _get_setup_message(has_profile, profile_complete, has_plan)
        }
    except Exception as e:
        return {
            "has_profile": False,
            "profile_complete": False,
            "has_budget_plan": False,
            "has_statement": False,
            "is_fully_setup": False,
            "missing_items": ["Unable to check status"],
            "next_step": None,
            "error": str(e)
        }


def _get_setup_message(has_profile: bool, profile_complete: bool, has_plan: bool) -> str:
    """Generate a helpful message based on user's setup status."""
    if not has_profile or not profile_complete:
        return "I'd love to help with your budget! First, let's set up your financial profile so I can give you personalized advice. Would you like to do that now?"
    elif not has_plan:
        return "You have your profile set up, but you haven't created a budget plan yet. A budget plan helps you track spending and reach your goals. Would you like to create one together?"
    else:
        return "You're all set up! I can help you track your spending, check your budget, or answer any financial questions."


def suggest_next_action(user_id: int) -> Dict[str, Any]:
    """
    Suggest the next action for the user based on their setup status.
    Use this to guide users who haven't completed their setup.
    """
    status = check_user_setup_status(user_id)

    if status.get("error"):
        return {
            "action": "retry",
            "message": "I'm having trouble checking your account status. Please try again.",
            "ui_action": None
        }

    if not status["has_profile"] or not status["profile_complete"]:
        return {
            "action": "complete_profile",
            "message": "Let's start by setting up your financial profile. This helps me understand your income, expenses, and financial goals so I can give you personalized advice.",
            "ui_action": "open_profile_setup",
            "cta_text": "Set Up Profile"
        }

    if not status["has_budget_plan"]:
        return {
            "action": "create_budget_plan",
            "message": "Now let's create your personalized budget plan. I'll help you allocate your income across different categories and set savings goals.",
            "ui_action": "open_budget_creator",
            "cta_text": "Create Budget Plan"
        }

    # User is fully set up
    return {
        "action": "none_required",
        "message": "You're all set! What would you like to know about your finances?",
        "ui_action": None,
        "suggestions": [
            "Show me my budget overview",
            "How am I doing on spending this month?",
            "Check my savings progress"
        ]
    }


# Tool definitions with explicit usage guidance
TOOL_DEFINITIONS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "check_user_setup_status",
            "description": "IMPORTANT: Call this tool FIRST before any other budget/financial tools when the user asks about their budget, spending, or finances. This checks if the user has completed their profile and created a budget plan. If they haven't, you should guide them to set up before showing budget data.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "integer",
                        "description": "The user's ID"
                    }
                },
                "required": ["user_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "suggest_next_action",
            "description": "Use this when the user needs guidance on what to do next, especially if they haven't set up their profile or budget plan. Returns a suggested action with a helpful message and UI action.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "integer",
                        "description": "The user's ID"
                    }
                },
                "required": ["user_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_budget_overview",
            "description": "Get the user's budget breakdown showing income and all expense categories. ONLY use this when the user explicitly asks to see their budget, spending breakdown, monthly plan, or where their money goes. IMPORTANT: Only call this if the user has a budget plan (check with check_user_setup_status first).",
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
            "description": "Check if the user is on track with their budget and spending pace. ONLY use when the user asks about affordability (can I afford X?), spending pace, budget status, or if they're overspending. IMPORTANT: Only call this if the user has a budget plan.",
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
            "name": "get_account_balance",
            "description": "Get the user's current account balance and available funds. ONLY use when the user asks about their balance, how much money they have, or available funds.",
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
            "description": "Get the user's progress toward their savings goals. ONLY use when the user asks about savings, saving goals, or their progress toward financial goals.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    }
]


# Tool executor registry
TOOL_EXECUTORS: Dict[str, Callable] = {
    "check_user_setup_status": lambda args: check_user_setup_status(args.get("user_id", 0)),
    "suggest_next_action": lambda args: suggest_next_action(args.get("user_id", 0)),
    "get_budget_overview": lambda args: get_budget_overview_data(),
    "get_spending_status": lambda args: get_spending_status_data(),
    "get_account_balance": lambda args: get_account_balance_data(),
    "get_savings_progress": lambda args: get_savings_progress_data(),
}


def execute_tool(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute a tool by name with the given arguments.

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
TOOL_TO_VISUAL_TYPE: Dict[str, str] = {
    "check_user_setup_status": None,
    "suggest_next_action": None,
    "get_budget_overview": "sankeyFlow",
    "get_spending_status": "burndownChart",
    "get_account_balance": None,
    "get_savings_progress": None,
}


def get_visual_type_for_tool(tool_name: str) -> str:
    """Get the visual payload type associated with a tool."""
    return TOOL_TO_VISUAL_TYPE.get(tool_name)
