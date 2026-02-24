"""
User Blueprint — profile, financial summary, top expenses, category preferences, nudges.
"""

import json
from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request

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
def get_financial_summary():
    user_id = request.args.get("userId")
    if not user_id:
        return jsonify({"error": "userId is required"}), 400
    try:
        user_id = int(user_id)
    except ValueError:
        return jsonify({"error": "Invalid userId"}), 400

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
def delete_statement():
    user_id = request.args.get("userId")
    if not user_id:
        return jsonify({"error": "userId is required"}), 400
    try:
        user_id = int(user_id)
    except ValueError:
        return jsonify({"error": "Invalid userId"}), 400

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


@user_bp.route("/user/profile/<int:user_id>", methods=["GET"])
def get_user_profile(user_id):
    user = get_user(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    profile = get_profile(user_id)
    profile_data = None
    if profile:
        profile_data = {
            "isStudent": profile.get('is_student'),
            "budgetingGoal": profile.get('budgeting_goal'),
            "strictnessLevel": profile.get('strictness_level'),
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


@user_bp.route("/user/profile/<int:user_id>", methods=["PUT"])
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
        if "budgetingGoal" in data:
            profile_updates['budgeting_goal'] = data["budgetingGoal"]
        if "strictnessLevel" in data:
            profile_updates['strictness_level'] = data["strictnessLevel"]
        if profile_updates:
            upsert_profile(user_id, **profile_updates)

    return jsonify({"status": "success"})


@user_bp.route("/user/top-expenses/<int:user_id>", methods=["GET"])
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


@user_bp.route("/user/category-preferences/<int:user_id>", methods=["GET"])
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
            }
            for p in prefs
        ]
    })


@user_bp.route("/user/category-preferences/<int:user_id>", methods=["PUT"])
def update_category_preferences(user_id):
    user = get_user(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    data = request.get_json()
    if not data or "categories" not in data:
        return jsonify({"error": "categories field is required"}), 400

    set_category_prefs(user_id, data["categories"])
    return jsonify({"status": "success"})


@user_bp.route("/user/nudges/<int:user_id>", methods=["GET"])
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

    import litellm

    system_prompt = (
        "You are a transaction parser. Extract transaction details from the user's spoken statement.\n"
        "Return ONLY a JSON object with these fields:\n"
        '  {"amount": <number or null>, "category": <string or null>, "store": <string or null>, "date": <ISO 8601 string or null>, "notes": <string or null>}\n'
        "Rules:\n"
        "- amount: the dollar amount spent, as a number (e.g. 10.50). Convert words like \"ten\" to 10.\n"
        "- category: one of Coffee, Food, Groceries, Transport, Entertainment, Shopping, Gas, or Other.\n"
        "- store: the merchant/store name if mentioned.\n"
        "- date: if a date is mentioned, use ISO 8601. If \"today\" or not mentioned, use null.\n"
        "- notes: any extra detail not captured above, or null.\n"
        "Return ONLY the JSON object. No markdown, no explanation, no extra text."
    )

    try:
        response = litellm.completion(
            model="claude-sonnet-4-5-20250929",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": statement},
            ],
            max_tokens=256,
        )
        raw = response.choices[0].message.content or ""

        # Extract JSON from response (find first { to last })
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1:
            import json as _json
            parsed = _json.loads(raw[start:end + 1])
            return jsonify(parsed)

        return jsonify({"amount": None, "category": None, "store": None, "date": None, "notes": None})

    except Exception as e:
        print(f"Parse transaction error: {e}")
        return jsonify({"amount": None, "category": None, "store": None, "date": None, "notes": None})


@user_bp.route("/user/transactions", methods=["POST"])
def save_manual_transaction():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    user_id = data.get("userId")
    if not user_id:
        return jsonify({"error": "userId is required"}), 400
    try:
        user_id = int(user_id)
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid userId"}), 400

    user = get_user(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    amount = data.get("amount")
    if not amount or float(amount) <= 0:
        return jsonify({"error": "amount must be greater than 0"}), 400

    entity = create_manual_transaction(
        user_id,
        amount=float(amount),
        category=data.get("category", "Other"),
        store=data.get("store"),
        date=data.get("date"),
        notes=data.get("notes"),
        source="voice",
    )

    return jsonify({
        "success": True,
        "transactionId": str(entity.key.id),
    }), 201
