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


# Tool definitions with explicit usage guidance
TOOL_DEFINITIONS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_budget_overview",
            "description": "Get the user's budget breakdown showing income and all expense categories. ONLY use this when the user explicitly asks to see their budget, spending breakdown, monthly plan, or where their money goes. Do NOT use for greetings or general conversation.",
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
            "description": "Check if the user is on track with their budget and spending pace. ONLY use when the user asks about affordability (can I afford X?), spending pace, budget status, or if they're overspending. Do NOT use for greetings.",
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
    "get_budget_overview": "sankeyFlow",
    "get_spending_status": "burndownChart",
    "get_account_balance": None,
    "get_savings_progress": None,
}


def get_visual_type_for_tool(tool_name: str) -> str:
    """Get the visual payload type associated with a tool."""
    return TOOL_TO_VISUAL_TYPE.get(tool_name)
