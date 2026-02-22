"""
Smart expense classification service for BudgetBuddy.
Classifies transactions as essential, discretionary, or mixed
using pre-seeded defaults, merchant history, user overrides, and LLM inference.
"""

import json
from typing import Optional, Tuple, List, Dict, Any


# Confidence threshold: after N consistent user classifications of the same
# merchant, auto-apply to remaining unclassified transactions from that merchant.
CONFIDENCE_THRESHOLD = 3

# Pre-seeded defaults by Plaid detailed category (personal_finance_category.detailed)
# Only unambiguous essentials — everything else stays unclassified until user teaches.
# See: https://plaid.com/documents/transactions-personal-finance-category-taxonomy.csv
PRE_SEEDED_DEFAULTS = {
    # Rent & Utilities
    "RENT_AND_UTILITIES_RENT": ("essential", 1.0),
    "RENT_AND_UTILITIES_GAS_AND_ELECTRICITY": ("essential", 1.0),
    "RENT_AND_UTILITIES_WATER": ("essential", 1.0),
    "RENT_AND_UTILITIES_SEWAGE_AND_WASTE_MANAGEMENT": ("essential", 1.0),
    "RENT_AND_UTILITIES_INTERNET_AND_CABLE": ("essential", 1.0),
    "RENT_AND_UTILITIES_TELEPHONE": ("essential", 1.0),
    "RENT_AND_UTILITIES_OTHER_UTILITIES": ("essential", 1.0),
    # Loan Payments
    "LOAN_PAYMENTS_MORTGAGE_PAYMENT": ("essential", 1.0),
    "LOAN_PAYMENTS_STUDENT_LOAN_PAYMENT": ("essential", 1.0),
    "LOAN_PAYMENTS_CAR_PAYMENT": ("essential", 1.0),
    "LOAN_PAYMENTS_CREDIT_CARD_PAYMENT": ("essential", 1.0),
    "LOAN_PAYMENTS_PERSONAL_LOAN_PAYMENT": ("essential", 1.0),
    "LOAN_PAYMENTS_OTHER_PAYMENT": ("essential", 1.0),
    # Medical
    "MEDICAL_DENTAL_CARE": ("essential", 1.0),
    "MEDICAL_EYE_CARE": ("essential", 1.0),
    "MEDICAL_NURSING_CARE": ("essential", 1.0),
    "MEDICAL_PHARMACIES_AND_SUPPLEMENTS": ("essential", 1.0),
    "MEDICAL_PRIMARY_CARE": ("essential", 1.0),
    "MEDICAL_OTHER_MEDICAL": ("essential", 1.0),
    # General Services (essential subset)
    "GENERAL_SERVICES_INSURANCE": ("essential", 1.0),
    "GENERAL_SERVICES_EDUCATION": ("essential", 1.0),
    "GENERAL_SERVICES_CHILDCARE": ("essential", 1.0),
}

# Fallback defaults by Plaid primary category (personal_finance_category.primary)
# Only unambiguous essentials
PRIMARY_CATEGORY_DEFAULTS = {
    "RENT_AND_UTILITIES": ("essential", 1.0),
    "LOAN_PAYMENTS": ("essential", 1.0),
    "MEDICAL": ("essential", 1.0),
}


def normalize_merchant_name(name: Optional[str]) -> str:
    """Normalize merchant name for consistent lookups."""
    if not name:
        return ""
    return name.lower().strip()


def classify_transaction(transaction, user_id: int, use_llm: bool = False) -> None:
    """
    Classify a single transaction in-place.
    Priority: user MerchantClassification → pre-seeded by detailed → pre-seeded by primary → LLM inference → unclassified.
    Skips income transactions (amount <= 0).
    """
    # Skip income / credits — only classify expenses
    if transaction.amount is not None and transaction.amount <= 0:
        return

    from db_models import MerchantClassification

    merchant = normalize_merchant_name(transaction.merchant_name)

    # 1. Check user's merchant classification
    if merchant:
        mc = MerchantClassification.query.filter_by(
            user_id=user_id,
            merchant_name=merchant
        ).first()
        if mc:
            _apply_classification(transaction, mc.classification, mc.essential_ratio)
            return

    # 2. Check pre-seeded defaults by detailed category
    detailed = transaction.category_detailed
    if detailed and detailed in PRE_SEEDED_DEFAULTS:
        classification, ratio = PRE_SEEDED_DEFAULTS[detailed]
        _apply_classification(transaction, classification, ratio)
        return

    # 3. Check pre-seeded defaults by primary category
    primary = transaction.category_primary
    if primary and primary in PRIMARY_CATEGORY_DEFAULTS:
        classification, ratio = PRIMARY_CATEGORY_DEFAULTS[primary]
        _apply_classification(transaction, classification, ratio)
        return

    # 4. LLM inference for unknown merchants
    if use_llm and merchant:
        result = llm_classify_merchant(merchant, transaction.category_primary, transaction.category_detailed, user_id)
        if result:
            classification, ratio = result
            _apply_classification(transaction, classification, ratio)
            # Store as inferred MerchantClassification for future lookups
            _store_inferred_classification(user_id, merchant, transaction.category_detailed, classification, ratio)
            return

    # 5. Default to unclassified
    transaction.sub_category = 'unclassified'
    transaction.essential_amount = None
    transaction.discretionary_amount = None


def _apply_classification(transaction, classification: str, essential_ratio: float) -> None:
    """Apply classification and compute split amounts on a transaction."""
    transaction.sub_category = classification
    amount = abs(transaction.amount) if transaction.amount else 0.0

    if classification == 'essential':
        transaction.essential_amount = round(amount * essential_ratio, 2)
        transaction.discretionary_amount = round(amount * (1.0 - essential_ratio), 2)
    elif classification == 'discretionary':
        transaction.essential_amount = round(amount * essential_ratio, 2)
        transaction.discretionary_amount = round(amount * (1.0 - essential_ratio), 2)
    elif classification == 'mixed':
        transaction.essential_amount = round(amount * essential_ratio, 2)
        transaction.discretionary_amount = round(amount * (1.0 - essential_ratio), 2)
    else:
        transaction.essential_amount = None
        transaction.discretionary_amount = None


def retroactively_reclassify(user_id: int, merchant_name: str, classification: str, essential_ratio: float) -> int:
    """
    Reclassify all transactions for a user matching a merchant name.
    Returns the count of reclassified transactions.
    """
    from db_models import db, Transaction, PlaidItem, PlaidAccount

    normalized = normalize_merchant_name(merchant_name)
    if not normalized:
        return 0

    # Get all account IDs for this user
    plaid_items = PlaidItem.query.filter_by(user_id=user_id).all()
    account_ids = []
    for item in plaid_items:
        for account in item.accounts:
            account_ids.append(account.id)

    if not account_ids:
        return 0

    # Find matching transactions
    transactions = Transaction.query.filter(
        Transaction.plaid_account_id.in_(account_ids),
        db.func.lower(Transaction.merchant_name) == normalized
    ).all()

    count = 0
    for txn in transactions:
        _apply_classification(txn, classification, essential_ratio)
        count += 1

    return count


def classify_new_transactions(transactions: list, user_id: int) -> None:
    """Batch classify a list of transactions."""
    for txn in transactions:
        classify_transaction(txn, user_id)


# =============================================================================
# LLM Inference for Unknown Merchants
# =============================================================================

LLM_CLASSIFICATION_PROMPT = """You are a financial transaction classifier. Given a merchant name and optional category hints, classify it as essential, discretionary, or mixed spending.

Definitions:
- **essential**: Necessary spending (groceries, rent, utilities, insurance, medical, gas, transit, basic household supplies)
- **discretionary**: Optional/luxury spending (coffee shops, restaurants, entertainment, shopping, travel, alcohol, hobbies)
- **mixed**: Merchants that typically sell both essential and discretionary items (Target, Walmart, Costco, Amazon, drug stores with cosmetics)

For mixed merchants, estimate the essential_ratio (0.0 to 1.0) — the fraction of a typical purchase that is essential spending.

{user_context}

Respond with ONLY valid JSON in this exact format:
{{"classification": "essential" or "discretionary" or "mixed", "essential_ratio": <float 0.0-1.0>, "reasoning": "<brief explanation>"}}"""


def _get_user_classification_context(user_id: int) -> str:
    """Build context from user's existing classifications to help LLM infer."""
    from db_models import MerchantClassification

    classifications = MerchantClassification.query.filter_by(user_id=user_id).limit(20).all()
    if not classifications:
        return ""

    essential = [mc.merchant_name for mc in classifications if mc.classification == 'essential']
    discretionary = [mc.merchant_name for mc in classifications if mc.classification == 'discretionary']
    mixed = [mc.merchant_name for mc in classifications if mc.classification == 'mixed']

    lines = ["This user has classified the following merchants:"]
    if essential:
        lines.append(f"  Essential: {', '.join(essential[:8])}")
    if discretionary:
        lines.append(f"  Discretionary: {', '.join(discretionary[:8])}")
    if mixed:
        lines.append(f"  Mixed: {', '.join(mixed[:8])}")

    return "\n".join(lines)


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
        system_prompt = LLM_CLASSIFICATION_PROMPT.format(user_context=user_context)

        agent = Agent(
            name="MerchantClassifier",
            instructions=system_prompt,
            model="claude-sonnet-4-5-20250929",  # Use Sonnet for fast, cheap classification
        )

        # Build the user message
        msg_parts = [f"Merchant: {merchant_name}"]
        if category_primary:
            msg_parts.append(f"Plaid primary category: {category_primary}")
        if category_detailed:
            msg_parts.append(f"Plaid detailed category: {category_detailed}")

        result = agent.run("\n".join(msg_parts))
        response_text = result.get("content", "")

        # Parse JSON response
        json_text = response_text
        if "```json" in response_text:
            json_text = response_text.split("```json")[1].split("```")[0]
        elif "```" in response_text:
            json_text = response_text.split("```")[1].split("```")[0]

        data = json.loads(json_text.strip())
        classification = data.get("classification", "").lower()
        essential_ratio = float(data.get("essential_ratio", 0.5))

        if classification not in ('essential', 'discretionary', 'mixed'):
            return None

        # Clamp ratio
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
    from db_models import db, MerchantClassification

    existing = MerchantClassification.query.filter_by(
        user_id=user_id,
        merchant_name=merchant_name
    ).first()

    if not existing:
        mc = MerchantClassification(
            user_id=user_id,
            merchant_name=merchant_name,
            plaid_category_detailed=category_detailed,
            classification=classification,
            essential_ratio=essential_ratio,
            confidence='inferred',
            classification_count=1
        )
        db.session.add(mc)


def llm_classify_merchants_batch(
    merchants: List[Dict[str, Any]],
    user_id: int
) -> List[Dict[str, Any]]:
    """
    Classify multiple unknown merchants in a single LLM call.
    Each merchant dict should have: name, category_primary, category_detailed.
    Returns list of {name, classification, essential_ratio, reasoning}.
    """
    if not merchants:
        return []

    try:
        from services.llm_service import Agent

        user_context = _get_user_classification_context(user_id)

        system_prompt = f"""You are a financial transaction classifier. Classify each merchant as essential, discretionary, or mixed spending.

Definitions:
- **essential**: Necessary spending (groceries, rent, utilities, insurance, medical, gas, transit)
- **discretionary**: Optional spending (coffee shops, restaurants, entertainment, shopping, travel)
- **mixed**: Both essential and discretionary items (Target, Walmart, Costco, Amazon)

For mixed merchants, estimate essential_ratio (0.0-1.0).

{user_context}

Respond with ONLY a JSON array:
[{{"name": "merchant", "classification": "essential|discretionary|mixed", "essential_ratio": 0.0-1.0}}]"""

        agent = Agent(
            name="BatchMerchantClassifier",
            instructions=system_prompt,
            model="claude-sonnet-4-5-20250929",
        )

        # Format merchant list
        lines = []
        for m in merchants[:20]:  # Limit to 20 per batch
            line = f"- {m['name']}"
            if m.get('category_primary'):
                line += f" (category: {m['category_primary']}"
                if m.get('category_detailed'):
                    line += f" / {m['category_detailed']}"
                line += ")"
            lines.append(line)

        result = agent.run("Classify these merchants:\n" + "\n".join(lines))
        response_text = result.get("content", "")

        # Parse JSON
        json_text = response_text
        if "```json" in response_text:
            json_text = response_text.split("```json")[1].split("```")[0]
        elif "```" in response_text:
            json_text = response_text.split("```")[1].split("```")[0]

        results = json.loads(json_text.strip())
        if not isinstance(results, list):
            return []

        # Validate and normalize
        validated = []
        for item in results:
            classification = item.get("classification", "").lower()
            if classification in ('essential', 'discretionary', 'mixed'):
                validated.append({
                    "name": item.get("name", ""),
                    "classification": classification,
                    "essential_ratio": max(0.0, min(1.0, float(item.get("essential_ratio", 0.5))))
                })

        return validated

    except Exception as e:
        print(f"Batch LLM classification failed: {e}")
        return []
