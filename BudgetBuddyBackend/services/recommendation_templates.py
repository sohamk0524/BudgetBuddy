"""
Template-based recommendation generators for BudgetBuddy.

Each template is a deterministic function that analyzes real transaction data
and returns a structured RecommendationItem dict — no LLM involved.
Templates are registered via decorator and run automatically by the
recommendations generator, which merges them with LLM-based recommendations.
"""

from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Callable

# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_TEMPLATE_REGISTRY: Dict[str, Callable[[int], Optional[Dict[str, Any]]]] = {}


def register_template(name: str):
    """Decorator to register a recommendation template generator."""
    def decorator(fn: Callable[[int], Optional[Dict[str, Any]]]):
        _TEMPLATE_REGISTRY[name] = fn
        return fn
    return decorator


def run_all_templates(user_id: int) -> List[Dict[str, Any]]:
    """Run every registered template, returning valid results (skipping None / errors)."""
    results: List[Dict[str, Any]] = []
    for name, generator in _TEMPLATE_REGISTRY.items():
        try:
            rec = generator(user_id)
            if rec is not None:
                results.append(rec)
        except Exception as e:
            print(f"Template '{name}' failed for user {user_id} (non-fatal): {e}")
    return results


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _fetch_food_transactions(user_id: int, days: int = 30) -> List[Dict[str, Any]]:
    """Fetch all FOOD_AND_DRINK transactions for the user from Plaid."""
    from db_models import get_active_plaid_items, get_accounts_for_item, get_transactions_since

    plaid_items = get_active_plaid_items(user_id)
    if not plaid_items:
        return []

    account_ids: List[int] = []
    for item in plaid_items:
        for account in get_accounts_for_item(item.key.id):
            account_ids.append(account.key.id)

    if not account_ids:
        return []

    since_date = (datetime.now() - timedelta(days=days)).date()
    transactions = get_transactions_since(account_ids, since_date)

    # Filter to food & drink, positive amounts only (expenses)
    food_txns = []
    for txn in transactions:
        if txn.get("category_primary") == "FOOD_AND_DRINK" and (txn.get("amount") or 0) > 0:
            food_txns.append({
                "date": txn.get("date"),
                "name": txn.get("name"),
                "merchant_name": txn.get("merchant_name"),
                "amount": txn.get("amount", 0),
                "category_detailed": txn.get("category_detailed"),
            })

    return food_txns


def _analyze_food_spending(food_txns: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Group food transactions by merchant and compute breakdown.

    Returns None if fewer than 3 transactions (not enough for insight).
    """
    if len(food_txns) < 3:
        return None

    merchant_data: Dict[str, Dict[str, Any]] = {}
    category_counts: Dict[str, float] = {}

    for txn in food_txns:
        merchant = txn.get("merchant_name") or txn.get("name") or "Unknown"
        if merchant not in merchant_data:
            merchant_data[merchant] = {"merchant": merchant, "amount": 0, "count": 0}
        merchant_data[merchant]["amount"] += txn["amount"]
        merchant_data[merchant]["count"] += 1

        cat = txn.get("category_detailed") or "FOOD_AND_DRINK"
        category_counts[cat] = category_counts.get(cat, 0) + txn["amount"]

    merchant_breakdown = sorted(merchant_data.values(), key=lambda m: m["amount"], reverse=True)
    total_food_spend = sum(m["amount"] for m in merchant_breakdown)

    # Top detailed categories by spend
    top_categories = sorted(category_counts.items(), key=lambda x: x[1], reverse=True)

    return {
        "total_food_spend": round(total_food_spend, 2),
        "merchant_breakdown": merchant_breakdown,
        "top_merchant": merchant_breakdown[0] if merchant_breakdown else None,
        "top_detailed_categories": [c[0] for c in top_categories[:3]],
    }


def _get_school_food_tip(user_id: int, analysis: Dict[str, Any]) -> Optional[str]:
    """If the user is a student, fetch a school-specific food tip via RAG."""
    try:
        from db_models import get_profile
        from services.school_rag import get_school_advice

        profile = get_profile(user_id)
        if not profile or not profile.get("is_student") or not profile.get("school"):
            return None

        top_merchant = analysis["top_merchant"]["merchant"] if analysis.get("top_merchant") else "restaurants"
        categories = ", ".join(
            c.replace("FOOD_AND_DRINK_", "").replace("_", " ").lower()
            for c in analysis.get("top_detailed_categories", [])
        ) or "food"

        query = f"cheaper alternatives to {top_merchant} and affordable {categories} near campus with student discounts"
        school_slug = profile.get("school")

        result = get_school_advice(query, school_slug)
        answer = result.get("answer", "")
        if not answer:
            return None

        # Extract first actionable sentence, truncate to ~120 chars
        tip = answer.split("\n")[0].strip().rstrip(".")
        if len(tip) > 120:
            tip = tip[:117] + "..."
        return tip

    except Exception as e:
        print(f"School food tip failed (non-fatal): {e}")
        return None


# ---------------------------------------------------------------------------
# Food spending template
# ---------------------------------------------------------------------------

@register_template("food_spending")
def food_spending_template(user_id: int) -> Optional[Dict[str, Any]]:
    """Analyze food spending and return a recommendation card with merchant breakdown."""
    food_txns = _fetch_food_transactions(user_id, days=30)
    analysis = _analyze_food_spending(food_txns)
    if analysis is None:
        return None

    total = analysis["total_food_spend"]
    breakdown = analysis["merchant_breakdown"]

    # Title
    title = f"${total:.0f} on food this month"

    # Description line 1: top 3 merchants
    top_3 = breakdown[:3]
    spots = ", ".join(f"{m['merchant']} (${m['amount']:.0f})" for m in top_3)
    description = f"Top spots: {spots}."

    # School-specific tip for students
    school_tip = _get_school_food_tip(user_id, analysis)
    if school_tip:
        description += f"\n{school_tip}."

    # Potential savings: 15% of top merchant spend
    top_merchant_spend = breakdown[0]["amount"] if breakdown else 0
    potential_savings = round(top_merchant_spend * 0.15, 2)

    return {
        "category": "spending",
        "title": title,
        "description": description,
        "potentialSavings": potential_savings,
        "priority": 1,
        "icon": "fork.knife",
    }
