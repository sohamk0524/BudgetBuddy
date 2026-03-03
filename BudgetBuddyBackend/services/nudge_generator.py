"""
Rules-based nudge generator for BudgetBuddy.
Compares actual spending (from Plaid transactions) against budget plan allocations
to generate actionable nudges without requiring LLM calls.
"""

import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional


def _display_name(raw_name: str) -> str:
    """Convert a Plaid category code to a human-readable display name."""
    from api.user import format_category_name
    return format_category_name(raw_name)


def generate_nudges(user_id: int) -> List[Dict[str, Any]]:
    """
    Generate smart nudges by comparing actual spending vs. budget plan.

    Returns a list of nudge dicts sorted by impact, max 5.
    Each nudge has: type, title, message, category (optional), potentialSavings (optional).
    """
    nudges = []

    # 1. Get actual spending from Plaid transactions (last 30 days)
    actual_by_category = _get_actual_spending(user_id)

    # 2. Get budget plan allocations
    plan_allocations = _get_plan_allocations(user_id)

    # 3. Compare actual vs. planned
    if actual_by_category and plan_allocations:
        nudges.extend(_compare_spending(actual_by_category, plan_allocations))
    elif not actual_by_category:
        # Fallback: try statement-based spending
        statement_spending = _get_statement_spending(user_id)
        if statement_spending and plan_allocations:
            nudges.extend(_compare_spending(statement_spending, plan_allocations))

    # 4. Add goal-related nudges
    goal_nudges = _get_goal_nudges(user_id)
    nudges.extend(goal_nudges)

    # 5. Sort by potential savings (higher impact first), then return top 5
    nudges.sort(key=lambda n: n.get("potentialSavings", 0), reverse=True)
    return nudges[:5]


def _get_actual_spending(user_id: int) -> Dict[str, float]:
    """Get actual spending by category from Plaid transactions (last 30 days)."""
    from db_models import get_active_plaid_items, get_accounts_for_item, get_transactions_since

    plaid_items = get_active_plaid_items(user_id)
    if not plaid_items:
        return {}

    account_ids = []
    for item in plaid_items:
        for account in get_accounts_for_item(item.key.id):
            account_ids.append(account.key.id)

    if not account_ids:
        return {}

    since_date = (datetime.now() - timedelta(days=30)).date()
    transactions = get_transactions_since(account_ids, since_date)

    category_totals = {}
    for txn in transactions:
        if (txn.get('amount') or 0) > 0:
            category = txn.get('category_primary') or "Uncategorized"
            category_totals[category] = category_totals.get(category, 0) + txn['amount']

    return category_totals


def _get_statement_spending(user_id: int) -> Dict[str, float]:
    """Fallback: get spending by category from uploaded statement."""
    from db_models import get_statement

    statement = get_statement(user_id)
    if not statement or not statement.get('llm_analysis'):
        return {}

    try:
        analysis = json.loads(statement['llm_analysis'])
        top_categories = analysis.get("top_categories", [])
        return {
            cat.get("category", "Other"): float(cat.get("amount", 0))
            for cat in top_categories
        }
    except (json.JSONDecodeError, TypeError):
        return {}


def _get_plan_allocations(user_id: int) -> Dict[str, float]:
    """Get budget category allocations from the latest plan."""
    from db_models import get_latest_plan

    plan_record = get_latest_plan(user_id)
    if not plan_record:
        return {}

    try:
        plan_data = json.loads(plan_record['plan_json'])
        categories = plan_data.get("categories", [])
        return {
            cat.get("name", ""): float(cat.get("amount", 0))
            for cat in categories
            if cat.get("name")
        }
    except (json.JSONDecodeError, TypeError):
        return {}


def _compare_spending(
    actual: Dict[str, float],
    planned: Dict[str, float]
) -> List[Dict[str, Any]]:
    """Compare actual vs planned spending and generate nudges."""
    nudges = []

    # Normalize category names for matching (lowercase)
    actual_lower = {k.lower(): (k, v) for k, v in actual.items()}
    planned_lower = {k.lower(): (k, v) for k, v in planned.items()}

    for key, (plan_name, plan_amount) in planned_lower.items():
        if plan_amount <= 0:
            continue

        # Try to find matching actual spending
        if key in actual_lower:
            actual_name, actual_amount = actual_lower[key]
        else:
            continue

        ratio = actual_amount / plan_amount

        if ratio > 1.1:  # Over budget by >10%
            overspend = actual_amount - plan_amount
            display = _display_name(plan_name)
            nudges.append({
                "type": "spending_reduction",
                "title": f"{display} Over Budget",
                "message": f"You're ${overspend:.0f} over your ${plan_amount:.0f} {display} budget — time to rein it in!",
                "category": display,
                "potentialSavings": round(overspend, 2)
            })
        elif ratio < 0.7:  # Under budget by >30%
            saved = plan_amount - actual_amount
            display = _display_name(plan_name)
            nudges.append({
                "type": "positive_reinforcement",
                "title": f"Crushing it on {display}!",
                "message": f"${saved:.0f} under budget — nice work, keep it going!",
                "category": display,
                "potentialSavings": 0
            })

    return nudges


def _get_goal_nudges(user_id: int) -> List[Dict[str, Any]]:
    """Generate nudges about savings goal progress."""
    from db_models import get_latest_plan

    plan_record = get_latest_plan(user_id)
    if not plan_record:
        return []

    try:
        plan_data = json.loads(plan_record['plan_json'])
        total_savings = plan_data.get("totalSavings", 0)

        if total_savings > 0:
            return [{
                "type": "goal_reminder",
                "title": "Stay on track",
                "message": f"You've got ${total_savings:.0f}/mo earmarked for savings — set it aside early!",
                "potentialSavings": 0,
            }]
    except (json.JSONDecodeError, TypeError):
        pass

    return []
