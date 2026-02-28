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

_FOOD_CATEGORY_KEYWORDS = {"food", "drink", "coffee", "restaurant", "dining", "grocery", "groceries"}


def _is_food_category(category: str) -> bool:
    """Check if a category string is food-related (case-insensitive)."""
    if not category:
        return False
    lower = category.lower().replace("_", " ").replace("&", " ")
    return any(kw in lower for kw in _FOOD_CATEGORY_KEYWORDS)


def _fetch_food_transactions(user_id: int, days: int = 30) -> List[Dict[str, Any]]:
    """Fetch all food-related transactions from both Plaid and manual (voice-logged) sources."""
    from db_models import get_active_plaid_items, get_accounts_for_item, get_transactions_since, get_manual_transactions

    food_txns = []
    since_date = (datetime.now() - timedelta(days=days)).date()

    # 1. Plaid transactions
    plaid_items = get_active_plaid_items(user_id)
    if plaid_items:
        account_ids: List[int] = []
        for item in plaid_items:
            for account in get_accounts_for_item(item.key.id):
                account_ids.append(account.key.id)

        if account_ids:
            transactions = get_transactions_since(account_ids, since_date)
            for txn in transactions:
                if txn.get("category_primary") == "FOOD_AND_DRINK" and (txn.get("amount") or 0) > 0:
                    food_txns.append({
                        "date": txn.get("date"),
                        "name": txn.get("name"),
                        "merchant_name": txn.get("merchant_name"),
                        "amount": txn.get("amount", 0),
                        "category_detailed": txn.get("category_detailed"),
                    })

    # 2. Manual (voice-logged) transactions
    manual_txns = get_manual_transactions(user_id)
    since_str = since_date.isoformat()
    for mt in manual_txns:
        mt_date = mt.get("date") or ""
        if mt_date < since_str:
            continue
        if _is_food_category(mt.get("category", "")) and (mt.get("amount") or 0) > 0:
            food_txns.append({
                "date": mt_date,
                "name": mt.get("notes") or mt.get("category") or "Voice Transaction",
                "merchant_name": mt.get("store"),
                "amount": mt.get("amount", 0),
                "category_detailed": mt.get("category"),
            })

    return food_txns


def _analyze_food_spending(food_txns: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Group food transactions by merchant and compute breakdown.

    Returns None if fewer than 3 transactions (not enough for insight).
    """
    if len(food_txns) < 2:
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


_FOOD_TIP_PROMPT = """You are a student budget assistant. From these search results, extract ONE specific local food tip for a student near {school} who frequently eats at: {merchants}.

Search results:
{context}

Return ONLY a single sentence naming a specific restaurant, deal, or discount that serves similar food to what the student already buys. Examples of good responses:
- "Ike's offers student discounts, and Woodstock's has $5 lunch slices"
- "Try Taqueria Davis for $8 burritos instead of $12 Chipotle bowls"
- "Shah's Halal has $7 combo plates — cheaper than McDonald's"

Pick the result most relevant to the type of food the student already eats. Do NOT return generic advice. If truly nothing specific is found, return: NONE"""


def _infer_cuisine_types(merchants: List[str]) -> List[str]:
    """Infer cuisine types from merchant names for better search queries."""
    cuisine_keywords = {
        "mexican": ["taco", "chipotle", "taqueria", "burrito", "qdoba", "del taco", "baja"],
        "fast food": ["mcdonald", "burger king", "wendy", "five guys", "jack in the box", "in-n-out", "carl"],
        "coffee": ["starbucks", "peet", "dutch bros", "philz", "coffee"],
        "pizza": ["domino", "pizza", "papa john", "little caesar"],
        "asian": ["panda express", "chinese", "thai", "sushi", "ramen", "pho"],
        "sandwich": ["subway", "jimmy john", "jersey mike", "ike"],
        "chicken": ["chick-fil-a", "popeye", "raising cane", "kfc", "wingstop"],
    }
    found = set()
    for merchant in merchants:
        lower = merchant.lower()
        for cuisine, keywords in cuisine_keywords.items():
            if any(kw in lower for kw in keywords):
                found.add(cuisine)
    return list(found) if found else ["affordable"]


def _get_school_food_tip(user_id: int, analysis: Dict[str, Any]) -> Optional[str]:
    """If the user is a student, search Tavily for a specific cheaper food alternative based on their actual spending."""
    try:
        import os
        import litellm
        from tavily import TavilyClient
        from db_models import get_profile
        from services.school_rag import SCHOOL_DISPLAY_NAMES

        profile = get_profile(user_id)
        if not profile or not profile.get("is_student") or not profile.get("school"):
            print(f"[food_tip] Skipped: is_student={profile.get('is_student') if profile else None}, school={profile.get('school') if profile else None}")
            return None

        tavily_key = os.environ.get("TAVILY_API_KEY")
        if not tavily_key:
            print("[food_tip] Skipped: TAVILY_API_KEY not set")
            return None

        # Build a search query from actual transaction data
        breakdown = analysis.get("merchant_breakdown", [])
        merchant_names = [m["merchant"] for m in breakdown[:3]]
        cuisine_types = _infer_cuisine_types(merchant_names)
        merchants_str = ", ".join(merchant_names) if merchant_names else "fast food"

        school_slug = profile.get("school")
        school_display = SCHOOL_DISPLAY_NAMES.get(
            school_slug, school_slug.replace("_", " ").title()
        )

        cuisine_phrase = " and ".join(cuisine_types)
        search_query = f"cheap {cuisine_phrase} restaurants near {school_display} campus student discounts"
        print(f"[food_tip] Search query: {search_query}")

        # Step 1: Search Tavily directly
        client = TavilyClient(api_key=tavily_key)
        search_results = client.search(
            query=search_query,
            search_depth="basic",
            max_results=5,
            include_answer=True,
        )

        results_list = search_results.get("results", [])
        tavily_answer = search_results.get("answer", "")

        if not results_list and not tavily_answer:
            return None

        # Step 2: Build context from Tavily's own answer + full snippets
        context_parts = []
        if tavily_answer:
            context_parts.append(f"Summary: {tavily_answer[:500]}")
        for r in results_list:
            content = r.get("content", "")[:400]
            if content:
                context_parts.append(f"- {content}")
        context = "\n".join(context_parts)

        # Step 3: One small LLM call to extract a single concrete tip
        response = litellm.completion(
            model="claude-haiku-4-5-20251001",
            messages=[{"role": "user", "content": _FOOD_TIP_PROMPT.format(
                school=school_display, merchants=merchants_str, context=context
            )}],
            max_tokens=100,
        )
        tip = response.choices[0].message.content.strip().strip('"')

        if not tip or "NONE" in tip.upper() or len(tip) < 10:
            return None

        if len(tip) > 120:
            tip = tip[:117].rsplit(" ", 1)[0] + "..."

        print(f"[food_tip] Extracted: {tip}")
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

    # Build a human-readable cuisine label from merchant names
    merchant_names = [m["merchant"] for m in breakdown[:3]]
    cuisine_types = _infer_cuisine_types(merchant_names)
    cuisine_label = " & ".join(cuisine_types) if cuisine_types else "food"

    # Title: "$31 spent on fast food & coffee"
    title = f"${total:.0f} spent on {cuisine_label}"

    # Description: just the school-specific recommendation
    school_tip = _get_school_food_tip(user_id, analysis)
    description = school_tip.rstrip(".") if school_tip else f"Top spots: {', '.join(merchant_names)}"

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
