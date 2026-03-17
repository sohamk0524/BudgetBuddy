"""
User Blueprint — profile, financial summary, top expenses, category preferences, nudges.
"""

import json
from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request

from middleware.auth import require_auth
from db_models import (
    get_user,
    update_user,
    get_profile,
    upsert_profile,
    get_statement,
    delete_statement_for_user,
    get_active_plaid_items,
    get_plaid_items,
    get_accounts_for_item,
    get_transactions_for_accounts,
    get_latest_plan,
    get_category_prefs,
    set_category_prefs,
    create_manual_transaction,
)

user_bp = Blueprint('user', __name__)

# Plaid category code → human-readable display name
CATEGORY_DISPLAY_NAMES = {
    "INCOME": "Income",
    "TRANSFER_IN": "Transfers In",
    "TRANSFER_OUT": "Transfers Out",
    "LOAN_PAYMENTS": "Loan Payments",
    "BANK_FEES": "Bank Fees",
    "ENTERTAINMENT": "Entertainment",
    "FOOD_AND_DRINK": "Food & Drink",
    "GENERAL_MERCHANDISE": "Shopping",
    "HOME_IMPROVEMENT": "Home Improvement",
    "MEDICAL": "Medical",
    "PERSONAL_CARE": "Personal Care",
    "GENERAL_SERVICES": "Services",
    "GOVERNMENT_AND_NON_PROFIT": "Government & Taxes",
    "TRANSPORTATION": "Transportation",
    "TRAVEL": "Travel",
    "RENT_AND_UTILITIES": "Rent & Utilities",
    "COFFEE": "Coffee",
    "GROCERIES": "Groceries",
    "RESTAURANTS": "Restaurants",
    "SHOPPING": "Shopping",
    "CLOTHING": "Clothing",
    "ELECTRONICS": "Electronics",
    "GAS": "Gas",
    "PARKING": "Parking",
    "PUBLIC_TRANSIT": "Public Transit",
    "RIDESHARE": "Rideshare",
    "AIRLINES": "Airlines",
    "LODGING": "Lodging",
    "SUBSCRIPTION": "Subscriptions",
    "GYM_AND_FITNESS": "Gym & Fitness",
    "UTILITIES": "Utilities",
    "INTERNET_AND_CABLE": "Internet & Cable",
    "PHONE": "Phone",
    "INSURANCE": "Insurance",
    "MORTGAGE": "Mortgage",
    "RENT": "Rent",
    "EDUCATION": "Education",
    "CHILDCARE": "Childcare",
    "PETS": "Pets",
    "CHARITY": "Charity",
    "INVESTMENTS": "Investments",
    "SAVINGS": "Savings",
    "TAXES": "Taxes",
    "GAMBLING": "Gambling",
    "ALCOHOL_AND_BARS": "Alcohol & Bars",
}


def format_category_name(raw_name: str) -> str:
    """Convert a Plaid category code to a human-readable display name."""
    if raw_name in CATEGORY_DISPLAY_NAMES:
        return CATEGORY_DISPLAY_NAMES[raw_name]
    return raw_name.replace("_", " ").title().replace(" And ", " & ")


@user_bp.route("/user/financial-summary", methods=["GET"])
@require_auth
def get_financial_summary():
    user_id = request.args.get("userId")
    if not user_id:
        return jsonify({"error": "userId is required"}), 400

    user = get_user(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    # --- Try Plaid first ---
    plaid_items = get_active_plaid_items(user_id)
    plaid_accounts = []
    for item in plaid_items:
        plaid_accounts.extend(get_accounts_for_item(item.key.id))

    if plaid_accounts:
        asset_types = {"depository", "investment"}
        liability_types = {"credit", "loan"}

        asset_total = sum(
            (a.get('balance_current') or 0) for a in plaid_accounts
            if a.get('account_type') in asset_types
        )
        liability_total = sum(
            (a.get('balance_current') or 0) for a in plaid_accounts
            if a.get('account_type') in liability_types
        )
        net_worth = round(asset_total - liability_total, 2)

        safe_to_spend = None
        latest_plan = get_latest_plan(user_id)
        if latest_plan:
            try:
                plan_data = json.loads(latest_plan['plan_json'])
                safe_to_spend = plan_data.get("safeToSpend")
            except (json.JSONDecodeError, TypeError):
                pass

        if safe_to_spend is None:
            safe_to_spend = sum(
                (a.get('balance_available') or a.get('balance_current') or 0)
                for a in plaid_accounts
                if a.get('account_type') == "depository"
            )

        safe_to_spend = round(max(0, safe_to_spend), 2)

        return jsonify({
            "hasData": True,
            "source": "plaid",
            "netWorth": net_worth,
            "safeToSpend": safe_to_spend,
            "statementInfo": None,
            "spendingBreakdown": None,
        })

    # --- Fall back to statement ---
    statement = get_statement(user_id)
    if statement:
        net_worth = statement.get('ending_balance', 0) or 0
        safe_to_spend = max(0, 0.08 * net_worth)

        statement_period = None
        start = statement.get('statement_start_date')
        end = statement.get('statement_end_date')
        if start and end:
            statement_period = f"{start} to {end}"

        created_at = statement.get('created_at')
        statement_info = {
            "filename": statement.get('filename'),
            "statementPeriod": statement_period,
            "uploadedAt": created_at.isoformat() if created_at else None,
        }

        spending_breakdown = None
        if statement.get('llm_analysis'):
            try:
                analysis = json.loads(statement['llm_analysis'])
                top_categories = analysis.get("top_categories", [])
                if top_categories:
                    spending_breakdown = [
                        {"category": cat.get("category", "Other"), "amount": float(cat.get("amount", 0))}
                        for cat in top_categories
                    ]
            except (json.JSONDecodeError, TypeError):
                pass

        return jsonify({
            "hasData": True,
            "source": "statement",
            "netWorth": round(net_worth, 2),
            "safeToSpend": round(safe_to_spend, 2),
            "statementInfo": statement_info,
            "spendingBreakdown": spending_breakdown,
        })

    return jsonify({
        "hasData": False,
        "source": "none",
        "netWorth": None,
        "safeToSpend": None,
        "statementInfo": None,
        "spendingBreakdown": None,
    })


@user_bp.route("/user/statement", methods=["DELETE"])
@require_auth
def delete_statement():
    user_id = request.args.get("userId")
    if not user_id:
        return jsonify({"error": "userId is required"}), 400

    statement = get_statement(user_id)
    if statement:
        if statement.get('gcs_path'):
            try:
                from services.gcs_service import delete_statement as gcs_delete
                gcs_delete(statement['gcs_path'])
            except Exception as e:
                print(f"Warning: failed to delete GCS file: {e}")
        delete_statement_for_user(user_id)

    return "", 204


@user_bp.route("/user/profile/<user_id>", methods=["GET"])
@require_auth
def get_user_profile(user_id):
    user = get_user(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    profile = get_profile(user_id)
    profile_data = None
    if profile:
        profile_data = {
            "isStudent": profile.get('is_student'),
            "weeklySpendingLimit": profile.get('weekly_spending_limit'),
            "strictnessLevel": profile.get('strictness_level'),
            "school": profile.get('school'),
        }

    plaid_items_data = []
    for item in get_plaid_items(user_id):
        accounts = [
            {
                "accountId": acc.get('account_id'),
                "name": acc.get('name'),
                "type": acc.get('account_type'),
                "subtype": acc.get('account_subtype'),
                "mask": acc.get('mask'),
                "balanceCurrent": acc.get('balance_current'),
            }
            for acc in get_accounts_for_item(item.key.id)
        ]
        plaid_items_data.append({
            "itemId": item.get('item_id'),
            "institutionName": item.get('institution_name'),
            "status": item.get('status'),
            "accounts": accounts,
        })

    return jsonify({
        "name": user.get('name'),
        "phoneNumber": user.get('phone_number'),
        "profile": profile_data,
        "plaidItems": plaid_items_data,
    })


@user_bp.route("/user/profile/<user_id>", methods=["PUT"])
@require_auth
def update_user_profile(user_id):
    user = get_user(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    if "name" in data:
        update_user(user_id, name=data["name"])

    profile = get_profile(user_id)
    if profile:
        profile_updates = {}
        if "isStudent" in data:
            profile_updates['is_student'] = data["isStudent"]
        if "weeklySpendingLimit" in data:
            try:
                profile_updates['weekly_spending_limit'] = float(data["weeklySpendingLimit"])
            except (TypeError, ValueError):
                pass
        if "strictnessLevel" in data:
            profile_updates['strictness_level'] = data["strictnessLevel"]
        if "school" in data:
            profile_updates['school'] = data["school"]
        if profile_updates:
            upsert_profile(user_id, **profile_updates)

    return jsonify({"status": "success"})


@user_bp.route("/user/top-expenses/<user_id>", methods=["GET"])
@require_auth
def get_top_expenses(user_id):
    user = get_user(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    days = request.args.get("days", 30, type=int)

    # Try Plaid transactions first
    plaid_items = get_active_plaid_items(user_id)
    account_ids = []
    for item in plaid_items:
        for account in get_accounts_for_item(item.key.id):
            account_ids.append(account.key.id)

    if account_ids:
        start_date = (datetime.now() - timedelta(days=days)).date().isoformat()
        transactions, _ = get_transactions_for_accounts(account_ids, start_date=start_date, limit=10000)

        category_data = {}
        for txn in transactions:
            if (txn.get('amount') or 0) > 0:
                cat = txn.get('category_primary') or "Uncategorized"
                if cat not in category_data:
                    category_data[cat] = {"amount": 0, "count": 0}
                category_data[cat]["amount"] += txn['amount']
                category_data[cat]["count"] += 1

        sorted_cats = sorted(category_data.items(), key=lambda x: x[1]["amount"], reverse=True)
        total = sum(v["amount"] for v in category_data.values())

        return jsonify({
            "source": "plaid",
            "topExpenses": [
                {
                    "category": format_category_name(cat),
                    "amount": round(data["amount"], 2),
                    "transactionCount": data["count"],
                }
                for cat, data in sorted_cats[:5]
            ],
            "totalSpending": round(total, 2),
            "period": days,
        })

    # Fallback to statement
    statement = get_statement(user_id)
    if statement and statement.get('llm_analysis'):
        try:
            analysis = json.loads(statement['llm_analysis'])
            top_categories = analysis.get("top_categories", [])
            expenses = [
                {
                    "category": cat.get("category", "Other"),
                    "amount": float(cat.get("amount", 0)),
                    "transactionCount": 0,
                }
                for cat in top_categories[:5]
            ]
            total = sum(e["amount"] for e in expenses)
            return jsonify({
                "source": "statement",
                "topExpenses": expenses,
                "totalSpending": round(total, 2),
                "period": days,
            })
        except (json.JSONDecodeError, TypeError):
            pass

    return jsonify({
        "source": "none",
        "topExpenses": [],
        "totalSpending": 0,
        "period": days,
    })


@user_bp.route("/user/category-preferences/<user_id>", methods=["GET"])
@require_auth
def get_category_preferences(user_id):
    user = get_user(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    prefs = get_category_prefs(user_id)
    return jsonify({
        "categories": [
            {
                "id": p.key.id,
                "categoryName": p.get('category_name'),
                "displayOrder": p.get('display_order'),
                "emoji": p.get('emoji'),
                "isBuiltin": p.get('is_builtin', True),
                "weeklyLimit": p.get('weekly_limit'),
            }
            for p in prefs
        ]
    })


@user_bp.route("/user/category-preferences/<user_id>", methods=["PUT"])
@require_auth
def update_category_preferences(user_id):
    user = get_user(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    data = request.get_json()
    if not data or "categories" not in data:
        return jsonify({"error": "categories field is required"}), 400

    categories = data["categories"]

    # Validate: max 10 total, unique names
    if len(categories) > 10:
        return jsonify({"error": "Maximum 10 categories allowed"}), 400

    seen = set()
    for cat in categories:
        name = cat.get('name', cat) if isinstance(cat, dict) else cat
        lower = name.lower()
        if lower in seen:
            return jsonify({"error": f"Duplicate category name: {name}"}), 400
        seen.add(lower)

    set_category_prefs(user_id, categories)
    return jsonify({"status": "success"})


@user_bp.route("/user/category-preferences/<user_id>/<category_name>", methods=["DELETE"])
@require_auth
def delete_custom_category(user_id, category_name):
    """Delete a custom category and migrate all its transactions to another category."""
    from db_models import get_client
    from google.cloud.datastore import query as ds_query
    PropertyFilter = ds_query.PropertyFilter

    user = get_user(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    migrate_to = request.args.get("migrate_to", "other")
    builtin = ('food', 'drink', 'groceries', 'transportation', 'entertainment', 'other')
    if category_name.lower() in builtin:
        return jsonify({"error": "Cannot delete built-in categories"}), 400

    # Remove the preference entity
    prefs = get_category_prefs(user_id)
    remaining = [p for p in prefs if (p.get('category_name') or '').lower() != category_name.lower()]

    # Rebuild preferences without the deleted category
    rebuilt = []
    for p in remaining:
        rebuilt.append({
            'name': p.get('category_name'),
            'emoji': p.get('emoji'),
            'isBuiltin': p.get('is_builtin', True),
        })
    set_category_prefs(user_id, rebuilt)

    # Migrate transactions with the deleted category
    client = get_client()
    migrated = 0

    # Migrate ManualTransactions
    query = client.query(kind='ManualTransaction')
    query.add_filter(filter=PropertyFilter('user_id', '=', user_id))
    query.add_filter(filter=PropertyFilter('sub_category', '=', category_name.lower()))
    for txn in query.fetch():
        txn['sub_category'] = migrate_to
        client.put(txn)
        migrated += 1

    # Migrate MerchantClassifications
    mc_query = client.query(kind='MerchantClassification')
    mc_query.add_filter(filter=PropertyFilter('user_id', '=', user_id))
    mc_query.add_filter(filter=PropertyFilter('classification', '=', category_name.lower()))
    for mc in mc_query.fetch():
        mc['classification'] = migrate_to
        client.put(mc)

    return jsonify({"status": "success", "migratedCount": migrated})


@user_bp.route("/user/nudges/<user_id>", methods=["GET"])
@require_auth
def get_nudges(user_id):
    user = get_user(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    from services.nudge_generator import generate_nudges
    nudges = generate_nudges(user_id)
    return jsonify({"nudges": nudges})


@user_bp.route("/user/parse-transaction", methods=["POST"])
def parse_transaction():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    statement = data.get("statement", "").strip()
    if not statement:
        return jsonify({"error": "statement is required"}), 400

    # Optional userId — if provided, include custom categories in the LLM prompt
    user_id = data.get("userId")

    from services.llm_service import Agent
    from datetime import date as date_type
    today = date_type.today().strftime("%Y-%m-%d")

    # Build category list — include user's custom categories if available
    category_names_title = ["Food", "Drink", "Groceries", "Transportation", "Entertainment", "Other"]
    category_names_lower = ["food", "drink", "groceries", "transportation", "entertainment", "other"]
    custom_context = ""
    if user_id:
        from services.classification_service import get_valid_categories_for_user
        all_cats = get_valid_categories_for_user(user_id)
        extra = [c for c in all_cats if c not in category_names_lower]
        if extra:
            category_names_title += [c.capitalize() for c in extra]
            category_names_lower += extra
            custom_context = f"\nThis user also has custom categories: {', '.join(extra)}. Use these if they are a better fit.\n"

    cats_title_str = ", ".join(category_names_title)
    cats_lower_str = ", ".join(category_names_lower)

    parse_agent = Agent(
        name="TransactionParser",
        instructions=(
            "You are a transaction parser. Extract transaction details from the user's spoken statement.\n"
            "Group items by merchant/store — create one transaction object per merchant.\n"
            f"Today's date is {today}.\n"
            f"{custom_context}"
            "Return ONLY a JSON object with this exact structure:\n"
            '{"transactions": [\n'
            '  {\n'
            '    "store": <merchant name as string, or null>,\n'
            '    "amount": <total amount for this store as a positive number>,\n'
            f'    "category": <one of: {cats_title_str}>,\n'
            '    "date": <YYYY-MM-DD string, use today if not mentioned>,\n'
            '    "notes": <string or null>,\n'
            '    "items": [\n'
            f'      {{"name": <item name string>, "price": <item price as number>, "classification": <one of: {cats_lower_str}>}}\n'
            '    ]\n'
            '  }\n'
            ']}\n'
            "Rules:\n"
            "- Create one transaction per merchant/store. Multiple stores = multiple transaction objects.\n"
            "- amount: total amount for that store as a positive number. Convert words like 'ten' to 10.\n"
            "- category: choose based on dominant item type or store name (e.g. coffee shop -> Drink, restaurant -> Food, clothing store -> Other).\n"
            "- items: list each item mentioned. If per-item prices are not stated, divide the store total evenly among items (round to 2 decimal places, put any remainder in the last item).\n"
            f"- classification: lowercase category for each item ({cats_lower_str}).\n"
            "- date: use the date mentioned, or today if not specified.\n"
            "- Return ONLY the JSON object. No markdown code blocks, no explanation."
        ),
        tools=None,
    )

    def _fallback():
        return jsonify({"transactions": [{"amount": None, "category": None, "store": None, "date": today, "notes": None, "items": []}]})

    try:
        result = parse_agent.run(statement)
        raw = result.get("content", "")

        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1:
            parsed = json.loads(raw[start:end + 1])
            transactions = parsed.get("transactions", [])
            if transactions:
                return jsonify({"transactions": transactions})

        return _fallback()

    except Exception as e:
        print(f"Parse transaction error: {e}")
        return _fallback()


@user_bp.route("/user/transactions", methods=["POST"])
@require_auth
def save_manual_transaction():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    user_id = data.get("userId")
    if not user_id:
        return jsonify({"error": "userId is required"}), 400

    user = get_user(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    amount = data.get("amount")
    if not amount or float(amount) <= 0:
        return jsonify({"error": "amount must be greater than 0"}), 400

    # Determine classification — use category as sub_category for the new system
    from services.classification_service import get_valid_categories_for_user
    valid_categories = get_valid_categories_for_user(user_id)
    category_value = data.get("category", "Other")
    sub_category = category_value.lower() if category_value.lower() in valid_categories else "unclassified"

    amt = float(amount)

    # Optional receipt items — serialised as JSON string for storage
    receipt_items_raw = data.get("receiptItems")
    receipt_items_json = None
    if receipt_items_raw and isinstance(receipt_items_raw, list):
        def _item_cat(it):
            # iOS sends "classification"; older saves used "category" — accept both
            return it.get("classification") or it.get("category", "other")
        receipt_items_json = json.dumps([
            {"name": it.get("name", ""), "price": float(it.get("price", 0)),
             "classification": _item_cat(it)}
            for it in receipt_items_raw
        ])
        # Recompute sub_category from dominant item spend if items provided
        totals: dict = {}
        for it in receipt_items_raw:
            cat = _item_cat(it).lower()
            price = float(it.get("price", 0))
            if price > 0:
                totals[cat] = totals.get(cat, 0) + price
        if totals:
            dominant = max(totals, key=lambda k: totals[k])
            if dominant in valid_categories:
                sub_category = dominant

    entity = create_manual_transaction(
        user_id,
        amount=amt,
        category=category_value,
        store=data.get("store"),
        date=data.get("date"),
        notes=data.get("notes"),
        source=data.get("source", "manual"),
        sub_category=sub_category,
        essential_amount=None,
        discretionary_amount=None,
        receipt_items=receipt_items_json,
    )

    # Build full transaction object matching GET /expenses response format
    mt_source = entity.get('source') or 'manual'
    mt_date = entity.get('date') or ''
    receipt_items_str = entity.get('receipt_items')
    parsed_items = None
    if receipt_items_str:
        try:
            parsed_items = json.loads(receipt_items_str)
        except (json.JSONDecodeError, TypeError):
            parsed_items = None

    transaction_obj = {
        "id": entity.key.id,
        "transactionId": f"manual-{entity.key.id}",
        "accountId": "",
        "amount": entity.get('amount') or 0,
        "date": mt_date,
        "authorizedDate": mt_date,
        "name": entity.get('notes') or entity.get('store') or entity.get('category') or 'Transaction',
        "merchantName": entity.get('store'),
        "categoryPrimary": entity.get('category'),
        "categoryDetailed": entity.get('category'),
        "pending": False,
        "paymentChannel": mt_source,
        "subCategory": entity.get('sub_category') or 'unclassified',
        "essentialAmount": None,
        "discretionaryAmount": None,
        "source": mt_source,
        "notes": entity.get('notes'),
        "receiptItems": parsed_items,
    }

    return jsonify({
        "success": True,
        "transactionId": str(entity.key.id),
        "transaction": transaction_obj,
    }), 201


@user_bp.route("/user/transactions/<int:transaction_id>", methods=["PUT"])
def update_manual_transaction_endpoint(transaction_id):
    from db_models import update_manual_transaction
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    amount = data.get("amount")
    if not amount or float(amount) <= 0:
        return jsonify({"error": "amount must be greater than 0"}), 400

    valid_categories = ('food', 'drink', 'groceries', 'transportation', 'entertainment', 'other')
    category_value = data.get("category", "Other")
    sub_category = category_value.lower() if category_value.lower() in valid_categories else "unclassified"
    amt = float(amount)

    receipt_items_raw = data.get("receiptItems")
    receipt_items_json = None
    if receipt_items_raw and isinstance(receipt_items_raw, list):
        def _item_cat_put(it):
            return it.get("classification") or it.get("category", "other")
        receipt_items_json = json.dumps([
            {"name": it.get("name", ""), "price": float(it.get("price", 0)),
             "classification": _item_cat_put(it)}
            for it in receipt_items_raw
        ])
        totals: dict = {}
        for it in receipt_items_raw:
            cat = _item_cat_put(it).lower()
            price = float(it.get("price", 0))
            if price > 0:
                totals[cat] = totals.get(cat, 0) + price
        if totals:
            dominant = max(totals, key=lambda k: totals[k])
            if dominant in valid_categories:
                sub_category = dominant

    entity = update_manual_transaction(
        transaction_id,
        amount=amt,
        category=category_value,
        store=data.get("store"),
        date=data.get("date"),
        notes=data.get("notes"),
        source=data.get("source", "manual"),
        sub_category=sub_category,
        receipt_items=receipt_items_json,
    )

    if entity is None:
        return jsonify({"error": "Transaction not found"}), 404

    return jsonify({"success": True, "transactionId": str(transaction_id)})


# ---------------------------------------------------------------------------
# Gamification
# ---------------------------------------------------------------------------

@user_bp.route("/user/gamification/<user_id>", methods=["GET"])
@require_auth
def get_gamification_data(user_id):
    """Return gamification stats: streak, total saved, weekly challenge, challenge history."""
    from db_models import get_gamification, upsert_gamification
    from services.gamification_service import (
        calculate_streak,
        generate_weekly_challenge,
        get_challenge_progress,
        archive_challenge,
    )

    user = get_user(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    gam = get_gamification(user_id)

    # Determine current ISO week
    now = datetime.utcnow()
    iso_year, iso_week, _ = now.isocalendar()
    current_week = f"{iso_year}-W{iso_week:02d}"

    # Recalculate streak if stale
    streak_week = gam.get('streak_updated_week') if gam else None
    if streak_week != current_week:
        current_streak, longest_streak = calculate_streak(user_id)
        upsert_gamification(
            user_id,
            savings_streak=current_streak,
            longest_streak=longest_streak,
            streak_updated_week=current_week,
        )
    else:
        current_streak = gam.get('savings_streak', 0) if gam else 0
        longest_streak = gam.get('longest_streak', 0) if gam else 0

    total_saved = float(gam.get('total_saved', 0)) if gam else 0
    challenges_enabled = gam.get('challenges_enabled', True) if gam else True

    # Generate or reuse weekly challenge
    challenge_week = gam.get('challenge_week') if gam else None
    challenge = None

    if challenge_week != current_week:
        # New week — archive the old challenge first (if any)
        old_challenge_json = gam.get('weekly_challenge_json', 'null') if gam else 'null'
        try:
            old_challenge = json.loads(old_challenge_json)
        except (json.JSONDecodeError, TypeError):
            old_challenge = None

        history_update = {}
        if old_challenge and old_challenge.get('accepted'):
            # Finalize progress before archiving
            old_challenge['currentSpent'] = get_challenge_progress(
                user_id, old_challenge['category']
            )
            history = archive_challenge(gam, old_challenge)
            history_update['challenge_history_json'] = json.dumps(history)

        # Generate new challenge only if enabled
        if challenges_enabled:
            challenge = generate_weekly_challenge(user_id)
            if challenge:
                challenge['currentSpent'] = get_challenge_progress(user_id, challenge['category'])

        upsert_gamification(
            user_id,
            weekly_challenge_json=json.dumps(challenge) if challenge else 'null',
            challenge_week=current_week,
            challenge_dismissed_this_week=False,
            **history_update,
        )
    else:
        # Same week — reuse existing challenge
        try:
            challenge = json.loads(gam.get('weekly_challenge_json', 'null')) if gam else None
        except (json.JSONDecodeError, TypeError):
            challenge = None
        if challenge:
            challenge['currentSpent'] = get_challenge_progress(user_id, challenge['category'])
        elif challenges_enabled and not gam.get('challenge_dismissed_this_week'):
            # No challenge stored but not explicitly dismissed — retry generation
            challenge = generate_weekly_challenge(user_id)
            if challenge:
                challenge['currentSpent'] = get_challenge_progress(user_id, challenge['category'])
                upsert_gamification(user_id, weekly_challenge_json=json.dumps(challenge))

    # Load challenge history
    history_json = gam.get('challenge_history_json', '[]') if gam else '[]'
    try:
        challenge_history = json.loads(history_json)
    except (json.JSONDecodeError, TypeError):
        challenge_history = []

    return jsonify({
        "savingsStreak": current_streak,
        "longestStreak": longest_streak,
        "totalSaved": total_saved,
        "challengesEnabled": challenges_enabled,
        "weeklyChallenge": challenge,
        "challengeHistory": challenge_history,
    })


@user_bp.route("/user/gamification/mark-used-savings", methods=["POST"])
@require_auth
def mark_used_savings():
    """Increment the user's total saved amount when they mark a tip as Used."""
    from db_models import get_gamification, upsert_gamification

    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    user_id = data.get("userId")
    amount = data.get("amount", 0)
    if not user_id:
        return jsonify({"error": "userId is required"}), 400

    try:
        amount = float(amount)
    except (TypeError, ValueError):
        amount = 0

    if amount > 0:
        gam = get_gamification(user_id)
        current_total = float(gam.get('total_saved', 0)) if gam else 0
        upsert_gamification(user_id, total_saved=current_total + amount)

    return jsonify({"success": True})


@user_bp.route("/user/gamification/challenge-response", methods=["POST"])
@require_auth
def challenge_response():
    """Accept, decline, or dismiss the weekly challenge."""
    from db_models import get_gamification, upsert_gamification
    from services.gamification_service import generate_weekly_challenge, get_challenge_progress, archive_challenge

    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    user_id = data.get("userId")
    action = data.get("action")  # "accept", "decline", or "dismiss"
    if not user_id or action not in ("accept", "decline", "dismiss"):
        return jsonify({"error": "userId and action (accept/decline/dismiss) required"}), 400

    gam = get_gamification(user_id)
    if not gam:
        return jsonify({"error": "No gamification data"}), 404

    if action == "accept":
        # Mark current challenge as accepted
        try:
            challenge = json.loads(gam.get('weekly_challenge_json', 'null'))
        except (json.JSONDecodeError, TypeError):
            challenge = None
        if challenge:
            challenge['accepted'] = True
            challenge['currentSpent'] = get_challenge_progress(user_id, challenge['category'])
            upsert_gamification(user_id, weekly_challenge_json=json.dumps(challenge))
            return jsonify({"weeklyChallenge": challenge})
        return jsonify({"error": "No challenge to accept"}), 404

    elif action == "dismiss":
        # Archive (if accepted) and remove for the rest of the week
        try:
            old_challenge = json.loads(gam.get('weekly_challenge_json', 'null'))
        except (json.JSONDecodeError, TypeError):
            old_challenge = None

        history_update = {}
        if old_challenge and old_challenge.get('accepted'):
            old_challenge['currentSpent'] = get_challenge_progress(user_id, old_challenge['category'])
            old_challenge['dismissed'] = True
            history = archive_challenge(gam, old_challenge)
            history_update['challenge_history_json'] = json.dumps(history)

        upsert_gamification(user_id, weekly_challenge_json='null', challenge_dismissed_this_week=True, **history_update)
        return jsonify({"weeklyChallenge": None})

    else:  # decline
        # Generate a new challenge, excluding the current category
        try:
            old_challenge = json.loads(gam.get('weekly_challenge_json', 'null'))
        except (json.JSONDecodeError, TypeError):
            old_challenge = None
        exclude_category = old_challenge.get('category') if old_challenge else None

        new_challenge = generate_weekly_challenge(user_id, exclude_category=exclude_category)
        if new_challenge:
            new_challenge['currentSpent'] = get_challenge_progress(user_id, new_challenge['category'])
            upsert_gamification(user_id, weekly_challenge_json=json.dumps(new_challenge))
            return jsonify({"weeklyChallenge": new_challenge})
        else:
            # No alternative — clear challenge
            upsert_gamification(user_id, weekly_challenge_json='null')
            return jsonify({"weeklyChallenge": None})


@user_bp.route("/user/gamification/toggle-challenges", methods=["POST"])
@require_auth
def toggle_challenges():
    """Enable or disable weekly challenge generation."""
    from db_models import get_gamification, upsert_gamification

    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    user_id = data.get("userId")
    enabled = data.get("enabled")
    if not user_id or enabled is None:
        return jsonify({"error": "userId and enabled (bool) required"}), 400

    upsert_gamification(user_id, challenges_enabled=bool(enabled))

    # If disabling, also clear current challenge
    if not enabled:
        upsert_gamification(user_id, weekly_challenge_json='null')

    return jsonify({"success": True, "challengesEnabled": bool(enabled)})
