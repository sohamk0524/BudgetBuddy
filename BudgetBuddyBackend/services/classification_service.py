"""
Smart expense classification service for BudgetBuddy.
Classifies transactions into categories: food, drink, transportation, entertainment, other
using pre-seeded defaults, merchant history, user overrides, and LLM inference.
"""

import json
from typing import Optional, Tuple, List, Dict, Any


# Confidence threshold: after N consistent user classifications of the same
# merchant, auto-apply to remaining unclassified transactions from that merchant.
CONFIDENCE_THRESHOLD = 3

VALID_CATEGORIES = ('food', 'drink', 'groceries', 'transportation', 'entertainment', 'other')

# Known category registry — keywords help the LLM classify into custom categories.
# When a user adds a custom category whose name matches a key here, the LLM prompt
# includes these keywords so it can accurately map merchants/transactions.
KNOWN_CATEGORY_KEYWORDS = {
    "food":            ["food", "restaurant", "dining", "eat", "meal", "lunch", "dinner", "breakfast", "fast food"],
    "drink":           ["drink", "coffee", "cafe", "tea", "starbucks", "boba", "bar", "smoothie", "juice", "beer", "wine"],
    "groceries":       ["grocery", "groceries", "supermarket", "trader joe", "walmart", "costco", "aldi", "whole foods"],
    "transportation":  ["transport", "gas", "uber", "lyft", "ride", "bus", "transit", "parking", "fuel", "taxi", "toll"],
    "entertainment":   ["entertainment", "movie", "streaming", "spotify", "netflix", "gaming", "concert", "theater"],
    "other":           ["miscellaneous"],
    "cosmetics":       ["cosmetics", "makeup", "beauty", "skincare", "sephora", "ulta", "mascara", "lipstick", "foundation"],
    "subscriptions":   ["subscription", "recurring", "monthly", "annual", "netflix", "spotify", "hulu", "apple", "membership"],
    "health":          ["health", "medical", "doctor", "pharmacy", "hospital", "dental", "therapy", "prescription", "cvs", "walgreens"],
    "fitness":         ["fitness", "gym", "workout", "yoga", "pilates", "peloton", "crossfit", "training"],
    "shopping":        ["shopping", "clothes", "shoes", "apparel", "fashion", "mall", "retail", "zara", "nordstrom"],
    "education":       ["education", "tuition", "school", "university", "course", "textbook", "udemy", "coursera"],
    "travel":          ["travel", "flight", "hotel", "airbnb", "booking", "vacation", "trip", "airline"],
    "pets":            ["pet", "pets", "vet", "veterinary", "dog", "cat", "petco", "petsmart", "grooming"],
    "home":            ["home", "rent", "mortgage", "utilities", "electric", "furniture", "ikea", "maintenance"],
    "gifts":           ["gift", "gifts", "present", "birthday", "holiday", "donation", "charity"],
    "tech":            ["tech", "electronics", "computer", "phone", "apple store", "best buy", "software"],
    "music":           ["music", "concert", "vinyl", "instrument", "guitar", "piano", "tickets", "festival"],
    "books":           ["book", "books", "kindle", "audible", "bookstore", "library", "reading"],
    "gaming":          ["gaming", "game", "playstation", "xbox", "nintendo", "steam", "twitch"],
    "utilities":       ["utility", "utilities", "electric", "water", "gas bill", "internet", "phone bill", "power"],
    "insurance":       ["insurance", "premium", "coverage", "deductible", "geico", "state farm"],
    "savings":         ["savings", "investment", "stock", "401k", "ira", "deposit", "robinhood", "vanguard"],
    "personal care":   ["personal care", "haircut", "salon", "barber", "spa", "nails", "manicure", "massage"],
    "clothing":        ["clothing", "clothes", "shoes", "apparel", "fashion", "dress", "jacket"],
    "repairs":         ["repair", "fix", "maintenance", "mechanic", "plumber", "electrician", "handyman"],
}


def get_valid_categories_for_user(user_id) -> tuple:
    """Return VALID_CATEGORIES + any custom categories the user has defined."""
    if not user_id:
        return VALID_CATEGORIES
    try:
        from db_models import get_user_custom_categories
        custom = get_user_custom_categories(user_id)
        if custom:
            return VALID_CATEGORIES + tuple(c.lower() for c in custom)
    except Exception:
        pass
    return VALID_CATEGORIES

# Pre-seeded defaults by Plaid detailed category (personal_finance_category.detailed)
# Maps Plaid categories to our 5 categories.
# See: https://plaid.com/documents/transactions-personal-finance-category-taxonomy.csv
PRE_SEEDED_DEFAULTS = {
    # Food & Drink → food or drink
    "FOOD_AND_DRINK_GROCERIES": ("groceries", 0.0),
    "FOOD_AND_DRINK_RESTAURANTS": ("food", 0.0),
    "FOOD_AND_DRINK_FAST_FOOD": ("food", 0.0),
    "FOOD_AND_DRINK_VENDING_MACHINES": ("food", 0.0),
    "FOOD_AND_DRINK_COFFEE": ("drink", 0.0),
    "FOOD_AND_DRINK_BEER_WINE_AND_LIQUOR": ("drink", 0.0),
    # Entertainment
    "ENTERTAINMENT_CASINOS_AND_GAMBLING": ("entertainment", 0.0),
    "ENTERTAINMENT_CONCERTS_AND_EVENTS": ("entertainment", 0.0),
    "ENTERTAINMENT_MOVIES_AND_MUSIC": ("entertainment", 0.0),
    "ENTERTAINMENT_SPORTING_EVENTS": ("entertainment", 0.0),
    "ENTERTAINMENT_TV_AND_MOVIES": ("entertainment", 0.0),
    "ENTERTAINMENT_VIDEO_GAMES": ("entertainment", 0.0),
    "ENTERTAINMENT_OTHER_ENTERTAINMENT": ("entertainment", 0.0),
    # Transportation
    "TRANSPORTATION_GAS": ("transportation", 0.0),
    "TRANSPORTATION_PARKING": ("transportation", 0.0),
    "TRANSPORTATION_PUBLIC_TRANSIT": ("transportation", 0.0),
    "TRANSPORTATION_TAXIS_AND_RIDE_SHARING": ("transportation", 0.0),
    # Everything else → other
    "RENT_AND_UTILITIES_RENT": ("other", 0.0),
    "RENT_AND_UTILITIES_GAS_AND_ELECTRICITY": ("other", 0.0),
    "RENT_AND_UTILITIES_WATER": ("other", 0.0),
    "RENT_AND_UTILITIES_SEWAGE_AND_WASTE_MANAGEMENT": ("other", 0.0),
    "RENT_AND_UTILITIES_INTERNET_AND_CABLE": ("other", 0.0),
    "RENT_AND_UTILITIES_TELEPHONE": ("other", 0.0),
    "RENT_AND_UTILITIES_OTHER_UTILITIES": ("other", 0.0),
    "LOAN_PAYMENTS_MORTGAGE_PAYMENT": ("other", 0.0),
    "LOAN_PAYMENTS_STUDENT_LOAN_PAYMENT": ("other", 0.0),
    "LOAN_PAYMENTS_CAR_PAYMENT": ("other", 0.0),
    "LOAN_PAYMENTS_CREDIT_CARD_PAYMENT": ("other", 0.0),
    "LOAN_PAYMENTS_PERSONAL_LOAN_PAYMENT": ("other", 0.0),
    "LOAN_PAYMENTS_OTHER_PAYMENT": ("other", 0.0),
    "MEDICAL_DENTAL_CARE": ("other", 0.0),
    "MEDICAL_EYE_CARE": ("other", 0.0),
    "MEDICAL_NURSING_CARE": ("other", 0.0),
    "MEDICAL_PHARMACIES_AND_SUPPLEMENTS": ("other", 0.0),
    "MEDICAL_PRIMARY_CARE": ("other", 0.0),
    "MEDICAL_OTHER_MEDICAL": ("other", 0.0),
    "GENERAL_SERVICES_INSURANCE": ("other", 0.0),
    "GENERAL_SERVICES_EDUCATION": ("other", 0.0),
    "GENERAL_SERVICES_CHILDCARE": ("other", 0.0),
    "TRAVEL_FLIGHTS": ("other", 0.0),
    "TRAVEL_LODGING": ("other", 0.0),
    "TRAVEL_RENTAL_CARS": ("other", 0.0),
    "GENERAL_MERCHANDISE_DISCOUNT_STORES": ("other", 0.0),
    "GENERAL_MERCHANDISE_ONLINE_MARKETPLACES": ("other", 0.0),
    "GENERAL_MERCHANDISE_SUPERSTORES": ("other", 0.0),
    "GOVERNMENT_AND_NON_PROFIT_TAX_PAYMENT": ("other", 0.0),
    "PERSONAL_CARE_HAIR_AND_BEAUTY": ("other", 0.0),
    "PERSONAL_CARE_GYMS_AND_FITNESS_CENTERS": ("other", 0.0),
    "PERSONAL_CARE_LAUNDRY_AND_DRY_CLEANING": ("other", 0.0),
}

# Fallback defaults by Plaid primary category (personal_finance_category.primary)
PRIMARY_CATEGORY_DEFAULTS = {
    "FOOD_AND_DRINK": ("food", 0.0),
    "ENTERTAINMENT": ("entertainment", 0.0),
    "TRANSPORTATION": ("transportation", 0.0),
    "RENT_AND_UTILITIES": ("other", 0.0),
    "LOAN_PAYMENTS": ("other", 0.0),
    "MEDICAL": ("other", 0.0),
    "TRAVEL": ("other", 0.0),
    "GENERAL_MERCHANDISE": ("other", 0.0),
    "PERSONAL_CARE": ("other", 0.0),
}

# Not used in new system but kept for import compatibility
OBVIOUSLY_DISCRETIONARY_CATEGORIES = set()


def normalize_merchant_name(name: Optional[str]) -> str:
    """Normalize merchant name for consistent lookups."""
    if not name:
        return ""
    return name.lower().strip()


def classify_transaction(transaction, user_id: int, use_llm: bool = False) -> None:
    """
    Classify a single Datastore transaction entity in-place and persist.
    Priority: user MerchantClassification → pre-seeded by detailed → pre-seeded by primary → LLM → unclassified.
    Skips income transactions (amount <= 0).
    Uses merchant_name if available, falls back to name field for merchant identity.
    """
    amount = transaction.get('amount')
    if amount is not None and amount <= 0:
        return

    from db_models import get_merchant_classification

    # Use merchant_name if set, fall back to transaction name for classification identity
    merchant = normalize_merchant_name(
        transaction.get('merchant_name') or transaction.get('name')
    )

    # 1. Check user's merchant classification
    if merchant:
        mc = get_merchant_classification(user_id, merchant)
        if mc:
            _apply_classification(transaction, mc['classification'], mc['essential_ratio'])
            _save_transaction(transaction)
            return

    # 2. Check pre-seeded defaults by detailed category
    detailed = transaction.get('category_detailed')
    if detailed and detailed in PRE_SEEDED_DEFAULTS:
        classification, ratio = PRE_SEEDED_DEFAULTS[detailed]
        _apply_classification(transaction, classification, ratio)
        _save_transaction(transaction)
        return

    # 3. Check pre-seeded defaults by primary category
    primary = transaction.get('category_primary')
    if primary and primary in PRIMARY_CATEGORY_DEFAULTS:
        classification, ratio = PRIMARY_CATEGORY_DEFAULTS[primary]
        _apply_classification(transaction, classification, ratio)
        _save_transaction(transaction)
        return

    # 4. LLM inference for unknown merchants
    if use_llm and merchant:
        result = llm_classify_merchant(merchant, primary, detailed, user_id)
        if result:
            classification, ratio = result
            _apply_classification(transaction, classification, ratio)
            _save_transaction(transaction)
            _store_inferred_classification(user_id, merchant, detailed, classification, ratio)
            return

    # 5. Default to unclassified — do not persist, leave sub_category as-is
    # (avoids overwriting auto-classify results due to Datastore eventual consistency)
    transaction['sub_category'] = transaction.get('sub_category') or 'unclassified'
    transaction['essential_amount'] = None
    transaction['discretionary_amount'] = None


def _save_transaction(transaction) -> None:
    """Persist a Datastore transaction entity."""
    from db_models import get_client
    get_client().put(transaction)


def _apply_classification(transaction, classification: str, essential_ratio: float = 0.0) -> None:
    """Apply classification on a Datastore transaction entity."""
    transaction['sub_category'] = classification
    transaction['essential_amount'] = None
    transaction['discretionary_amount'] = None


def retroactively_reclassify(user_id: int, merchant_name: str, classification: str, essential_ratio: float) -> int:
    """
    Reclassify all transactions for a user matching a merchant name.
    Returns the count of reclassified transactions.
    """
    from db_models import get_plaid_items, get_accounts_for_item, get_client
    from google.cloud.datastore.query import PropertyFilter

    normalized = normalize_merchant_name(merchant_name)
    if not normalized:
        return 0

    account_ids = []
    for item in get_plaid_items(user_id):
        for account in get_accounts_for_item(item.key.id):
            account_ids.append(account.key.id)

    if not account_ids:
        return 0

    client = get_client()
    count = 0
    for account_id in account_ids:
        query = client.query(kind='Transaction')
        query.add_filter(filter=PropertyFilter('plaid_account_id', '=', account_id))
        for txn in query.fetch():
            # Match on merchant_name first, fall back to name field (same as classify_transaction)
            effective = normalize_merchant_name(
                txn.get('merchant_name') or txn.get('name')
            )
            if effective == normalized:
                _apply_classification(txn, classification, essential_ratio)
                client.put(txn)
                count += 1

    return count


def classify_new_transactions(transactions: list, user_id: int) -> None:
    """Batch classify a list of Datastore transaction entities."""
    for txn in transactions:
        classify_transaction(txn, user_id)


# =============================================================================
# LLM Inference for Unknown Merchants
# =============================================================================

LLM_CLASSIFICATION_PROMPT = """You are a financial transaction classifier. Given a merchant name and optional category hints, classify it into one of these categories: food, drink, groceries, transportation, entertainment, or other.

Definitions:
- **groceries**: Supermarkets, grocery stores, wholesale clubs (Walmart, Costco, Trader Joe's, Whole Foods, Safeway, Kroger, etc.)
- **food**: Restaurants, fast food, food delivery (not grocery stores)
- **drink**: Coffee shops, bars, alcohol stores, beverage shops
- **transportation**: Gas, parking, public transit, ride sharing, car expenses
- **entertainment**: Movies, music, games, concerts, events, streaming services
- **other**: Everything else (rent, utilities, medical, insurance, shopping, personal care, travel, etc.)

{user_context}

Respond with ONLY valid JSON in this exact format:
{{"classification": "food" or "drink" or "transportation" or "entertainment" or "other", "essential_ratio": 0.0, "reasoning": "<brief explanation>"}}"""


def _get_user_classification_context(user_id: int) -> str:
    """Build context from user's existing classifications to help LLM infer."""
    from db_models import get_merchant_classifications_for_user

    classifications = get_merchant_classifications_for_user(user_id)[:20]
    if not classifications:
        return ""

    by_cat = {}
    for mc in classifications:
        cat = mc.get('classification', 'other')
        if cat not in by_cat:
            by_cat[cat] = []
        by_cat[cat].append(mc['merchant_name'])

    lines = ["This user has classified the following merchants:"]
    for cat, merchants in by_cat.items():
        lines.append(f"  {cat.capitalize()}: {', '.join(merchants[:8])}")

    return "\n".join(lines)


def _build_custom_category_context(user_id: int) -> str:
    """Build additional LLM context about user's custom categories, with keyword hints."""
    try:
        from db_models import get_user_custom_categories
        custom = get_user_custom_categories(user_id)
        if not custom:
            return ""
        lines = ["\nThis user also has custom categories. Use these if they are a better fit than the standard categories:"]
        for cat_name in custom:
            key = cat_name.lower()
            keywords = KNOWN_CATEGORY_KEYWORDS.get(key)
            if keywords:
                lines.append(f"  - {cat_name}: includes {', '.join(keywords[:8])}")
            else:
                lines.append(f"  - {cat_name}")
        return "\n".join(lines)
    except Exception:
        pass
    return ""


def llm_classify_merchant(
    merchant_name: str,
    category_primary: Optional[str],
    category_detailed: Optional[str],
    user_id: int
) -> Optional[Tuple[str, float]]:
    """
    Use LLM to infer classification for an unknown merchant.
    Returns (classification, essential_ratio) or None if LLM is unavailable.
    """
    try:
        from services.llm_service import Agent

        user_context = _get_user_classification_context(user_id)
        user_context += _build_custom_category_context(user_id)
        valid_cats = get_valid_categories_for_user(user_id)
        system_prompt = LLM_CLASSIFICATION_PROMPT.format(user_context=user_context)

        agent = Agent(
            name="MerchantClassifier",
            instructions=system_prompt,
            model="claude-haiku-4-5-20251001",
        )

        msg_parts = [f"Merchant: {merchant_name}"]
        if category_primary:
            msg_parts.append(f"Plaid primary category: {category_primary}")
        if category_detailed:
            msg_parts.append(f"Plaid detailed category: {category_detailed}")

        result = agent.run("\n".join(msg_parts))
        response_text = result.get("content", "")

        json_text = response_text
        if "```json" in response_text:
            json_text = response_text.split("```json")[1].split("```")[0]
        elif "```" in response_text:
            json_text = response_text.split("```")[1].split("```")[0]

        data = json.loads(json_text.strip())
        classification = data.get("classification", "").lower()
        essential_ratio = float(data.get("essential_ratio", 0.5))

        if classification not in valid_cats:
            return None

        essential_ratio = max(0.0, min(1.0, essential_ratio))
        return (classification, essential_ratio)

    except Exception as e:
        print(f"LLM classification failed for '{merchant_name}': {e}")
        return None


def _store_inferred_classification(
    user_id: int,
    merchant_name: str,
    category_detailed: Optional[str],
    classification: str,
    essential_ratio: float
) -> None:
    """Store an LLM-inferred classification for future lookups."""
    from db_models import get_merchant_classification, upsert_merchant_classification

    if not get_merchant_classification(user_id, merchant_name):
        upsert_merchant_classification(
            user_id, merchant_name,
            plaid_category_detailed=category_detailed,
            classification=classification,
            essential_ratio=essential_ratio,
            confidence='inferred',
            classification_count=1,
        )


def llm_classify_merchants_batch(
    merchants: List[Dict[str, Any]],
    user_id: int
) -> List[Dict[str, Any]]:
    """
    Classify multiple unknown merchants in a single LLM call.
    Each merchant dict should have: name, category_primary, category_detailed.
    Returns list of {name, classification, essential_ratio}.
    """
    if not merchants:
        return []

    try:
        from services.llm_service import Agent

        user_context = _get_user_classification_context(user_id)
        custom_context = _build_custom_category_context(user_id)
        valid_cats = get_valid_categories_for_user(user_id)
        cats_str = "|".join(valid_cats)

        system_prompt = f"""You are a financial transaction classifier. Classify each merchant into one of these categories: {", ".join(valid_cats)}.

Definitions:
- **groceries**: Supermarkets, grocery stores, wholesale clubs (Walmart, Costco, Trader Joe's, Whole Foods, Safeway, Kroger, etc.)
- **food**: Restaurants, fast food, food delivery (not grocery stores)
- **drink**: Coffee shops, bars, alcohol stores, beverage shops
- **transportation**: Gas, parking, public transit, ride sharing, car expenses
- **entertainment**: Movies, music, games, concerts, events, streaming services
- **other**: Everything else (rent, utilities, medical, insurance, shopping, personal care, travel, etc.)

{user_context}{custom_context}

Respond with ONLY a JSON array:
[{{"name": "merchant", "classification": "{cats_str}", "essential_ratio": 0.0}}]"""

        agent = Agent(
            name="BatchMerchantClassifier",
            instructions=system_prompt,
            model="claude-haiku-4-5-20251001",
        )

        lines = []
        for m in merchants[:20]:
            line = f"- {m['name']}"
            if m.get('category_primary'):
                line += f" (category: {m['category_primary']}"
                if m.get('category_detailed'):
                    line += f" / {m['category_detailed']}"
                line += ")"
            lines.append(line)

        result = agent.run("Classify these merchants:\n" + "\n".join(lines))
        response_text = result.get("content", "")

        json_text = response_text
        if "```json" in response_text:
            json_text = response_text.split("```json")[1].split("```")[0]
        elif "```" in response_text:
            json_text = response_text.split("```")[1].split("```")[0]

        results = json.loads(json_text.strip())
        if not isinstance(results, list):
            return []

        validated = []
        for item in results:
            classification = item.get("classification", "").lower()
            if classification in valid_cats:
                validated.append({
                    "name": item.get("name", ""),
                    "classification": classification,
                    "essential_ratio": max(0.0, min(1.0, float(item.get("essential_ratio", 0.5))))
                })

        return validated

    except Exception as e:
        print(f"Batch LLM classification failed: {e}")
        return []
