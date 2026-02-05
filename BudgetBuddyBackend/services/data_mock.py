"""
Mock data service for BudgetBuddy.
Provides realistic hardcoded financial data for the prototype.
"""

import uuid
from typing import List, Dict, Any
from datetime import datetime, timedelta
from models import SankeyNode


# Design System Colors
class Colors:
    TEAL = "#2DD4BF"
    PURPLE = "#A855F7"
    CORAL = "#F43F5E"
    SLATE = "#1E293B"
    GREEN = "#22C55E"
    AMBER = "#F59E0B"


# ============================================
# USER FINANCIAL DATA (Realistic Mock Data)
# ============================================

# Monthly income and budget settings
USER_PROFILE = {
    "name": "Alex",
    "monthly_income": 5500.00,
    "monthly_budget": 4500.00,  # Planned spending budget (excluding savings)
    "savings_target": 1000.00,  # Monthly savings goal
}

# Current month spending by category
CURRENT_MONTH_SPENDING = {
    "Rent": 1500.00,
    "Groceries": 387.50,
    "Utilities": 145.00,
    "Transportation": 220.00,
    "Dining Out": 185.00,
    "Entertainment": 95.00,
    "Shopping": 245.00,
    "Subscriptions": 65.00,
    "Healthcare": 0.00,
    "Other": 45.00,
}

# Budget allocations by category
BUDGET_ALLOCATIONS = {
    "Rent": 1500.00,
    "Groceries": 500.00,
    "Utilities": 200.00,
    "Transportation": 300.00,
    "Dining Out": 250.00,
    "Entertainment": 150.00,
    "Shopping": 300.00,
    "Subscriptions": 100.00,
    "Healthcare": 100.00,
    "Other": 100.00,
}

# Account balances
ACCOUNT_BALANCES = {
    "checking": 2847.50,
    "savings": 8500.00,
    "credit_card_balance": 450.00,
    "credit_card_limit": 5000.00,
}

# Savings goals
SAVINGS_GOALS = [
    {"name": "Emergency Fund", "target": 15000.00, "current": 8500.00},
    {"name": "Vacation", "target": 3000.00, "current": 1200.00},
    {"name": "New Laptop", "target": 2000.00, "current": 650.00},
]


# ============================================
# DATA RETRIEVAL FUNCTIONS
# ============================================

def get_budget_overview_data() -> Dict[str, Any]:
    """
    Get complete budget overview data for Sankey flow visualization.
    Returns income sources flowing to expense categories.
    """
    total_income = USER_PROFILE["monthly_income"]
    total_spent = sum(CURRENT_MONTH_SPENDING.values())
    savings = USER_PROFILE["savings_target"]

    nodes = [
        # Income node
        SankeyNode(id=str(uuid.uuid4()), name="Income", value=total_income),
    ]

    # Add expense category nodes (only those with spending > 0)
    for category, amount in CURRENT_MONTH_SPENDING.items():
        if amount > 0:
            nodes.append(SankeyNode(id=str(uuid.uuid4()), name=category, value=amount))

    # Add savings node
    nodes.append(SankeyNode(id=str(uuid.uuid4()), name="Savings", value=savings))

    # Add remaining/unallocated
    remaining = total_income - total_spent - savings
    if remaining > 0:
        nodes.append(SankeyNode(id=str(uuid.uuid4()), name="Available", value=remaining))

    return {
        "nodes": [node.to_dict() for node in nodes],
        "summary": {
            "total_income": total_income,
            "total_spent": total_spent,
            "savings": savings,
            "remaining": total_income - total_spent - savings
        }
    }


def get_spending_status_data() -> Dict[str, Any]:
    """
    Get current spending status for burndown chart visualization.
    Shows spent vs budget with pace tracking.
    """
    today = datetime.now()
    days_in_month = 30  # Simplified
    day_of_month = min(today.day, days_in_month)
    days_remaining = days_in_month - day_of_month

    total_budget = USER_PROFILE["monthly_budget"]
    total_spent = sum(CURRENT_MONTH_SPENDING.values())

    # Calculate ideal pace (linear spending)
    ideal_daily_spend = total_budget / days_in_month
    ideal_pace = ideal_daily_spend * day_of_month

    # Calculate spending rate
    if day_of_month > 0:
        actual_daily_rate = total_spent / day_of_month
        projected_end_of_month = actual_daily_rate * days_in_month
    else:
        actual_daily_rate = 0
        projected_end_of_month = 0

    # Determine status
    if total_spent <= ideal_pace * 0.9:
        status = "under_budget"
        status_message = "Great job! You're spending less than planned."
    elif total_spent <= ideal_pace * 1.1:
        status = "on_track"
        status_message = "You're on track with your budget."
    else:
        status = "over_budget"
        status_message = "Heads up! You're spending faster than planned."

    # Build detailed category analysis for LLM to use
    category_analysis = []
    for category, spent in CURRENT_MONTH_SPENDING.items():
        budgeted = BUDGET_ALLOCATIONS.get(category, 0)
        remaining = budgeted - spent
        pct_used = (spent / budgeted * 100) if budgeted > 0 else 0
        status_cat = "over_budget" if spent > budgeted else ("on_track" if pct_used > 70 else "under_budget")
        category_analysis.append({
            "category": category,
            "spent": spent,
            "budgeted": budgeted,
            "remaining": remaining,
            "percentUsed": round(pct_used, 1),
            "status": status_cat
        })

    # Sort by spending amount (highest first) for easy identification of top spending areas
    category_analysis.sort(key=lambda x: x["spent"], reverse=True)

    # Identify top spending categories and potential savings opportunities
    top_discretionary = [c for c in category_analysis if c["category"] in ["Dining Out", "Entertainment", "Shopping", "Subscriptions"] and c["spent"] > 0]
    over_budget_categories = [c for c in category_analysis if c["status"] == "over_budget"]

    return {
        "spent": total_spent,
        "budget": total_budget,
        "remaining": total_budget - total_spent,
        "idealPace": round(ideal_pace, 2),
        "dayOfMonth": day_of_month,
        "daysRemaining": days_remaining,
        "dailyBudgetRemaining": round((total_budget - total_spent) / max(days_remaining, 1), 2),
        "projectedEndOfMonth": round(projected_end_of_month, 2),
        "status": status,
        "statusMessage": status_message,
        "categoryBreakdown": CURRENT_MONTH_SPENDING.copy(),
        "categoryAnalysis": category_analysis,
        "topDiscretionarySpending": top_discretionary[:3],
        "overBudgetCategories": over_budget_categories,
        "savingOpportunities": [
            f"Reduce {c['category']} by ${min(50, c['spent'] * 0.2):.0f}/month"
            for c in top_discretionary[:2] if c["spent"] > 50
        ]
    }


def get_account_balance_data() -> Dict[str, Any]:
    """
    Get current account balance information.
    """
    checking = ACCOUNT_BALANCES["checking"]
    savings = ACCOUNT_BALANCES["savings"]
    credit_used = ACCOUNT_BALANCES["credit_card_balance"]
    credit_limit = ACCOUNT_BALANCES["credit_card_limit"]

    return {
        "checking_balance": checking,
        "savings_balance": savings,
        "total_liquid": checking + savings,
        "credit_card_balance": credit_used,
        "credit_available": credit_limit - credit_used,
        "net_worth": checking + savings - credit_used,
        "summary": f"You have ${checking:,.2f} in checking and ${savings:,.2f} in savings."
    }


def get_savings_progress_data() -> Dict[str, Any]:
    """
    Get savings goals progress information.
    """
    goals = []
    for goal in SAVINGS_GOALS:
        progress_pct = (goal["current"] / goal["target"]) * 100
        goals.append({
            "name": goal["name"],
            "target": goal["target"],
            "current": goal["current"],
            "remaining": goal["target"] - goal["current"],
            "progress_percent": round(progress_pct, 1)
        })

    total_saved = sum(g["current"] for g in SAVINGS_GOALS)
    total_target = sum(g["target"] for g in SAVINGS_GOALS)

    return {
        "goals": goals,
        "total_saved": total_saved,
        "total_target": total_target,
        "overall_progress": round((total_saved / total_target) * 100, 1),
        "monthly_savings_target": USER_PROFILE["savings_target"]
    }


# ============================================
# LEGACY FUNCTIONS (for backwards compatibility)
# ============================================

def get_sankey_flow_nodes() -> List[SankeyNode]:
    """Legacy function - returns Sankey nodes for budget overview."""
    data = get_budget_overview_data()
    return [SankeyNode(**node) for node in data["nodes"]]


def get_burndown_data() -> dict:
    """Legacy function - returns basic burndown data."""
    status = get_spending_status_data()
    return {
        "spent": status["spent"],
        "budget": status["budget"],
        "ideal_pace": status["idealPace"]
    }


def get_overspending_burndown_data() -> dict:
    """Legacy function - returns overspending scenario data."""
    return {
        "spent": 1250.0,
        "budget": 2000.0,
        "ideal_pace": 900.0
    }
