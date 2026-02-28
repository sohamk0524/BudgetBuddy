"""
Expenses Blueprint — classification, merchant preferences, device tokens.
"""

from flask import Blueprint, jsonify, request

from db_models import (
    get_user,
    get_plaid_items,
    get_accounts_for_item,
    get_transactions_for_accounts,
    get_merchant_classification,
    get_merchant_classifications_for_user,
    upsert_merchant_classification,
    get_device_token,
    upsert_device_token,
    get_client,
    get_manual_transactions,
)
from services.classification_service import (
    classify_transaction,
    retroactively_reclassify,
    normalize_merchant_name,
    llm_classify_merchants_batch,
    CONFIDENCE_THRESHOLD,
)

expenses_bp = Blueprint('expenses', __name__)


def _get_account_ids_and_map(user_id):
    """Return (account_ids list, account_id_map {internal_key_id: plaid_account_id_str})."""
    account_ids = []
    account_id_map = {}
    for item in get_plaid_items(user_id):
        for account in get_accounts_for_item(item.key.id):
            account_ids.append(account.key.id)
            account_id_map[account.key.id] = account.get('account_id', '')
    return account_ids, account_id_map


@expenses_bp.route("/expenses/<int:user_id>", methods=["GET"])
def get_expenses(user_id):
    """
    Get expenses with sub-category classification data.
    Auto-classifies any unclassified transactions on first access (lazy backfill).

    Query params: startDate, endDate, category, subCategory, limit, offset
    """
    user = get_user(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    start_date = request.args.get("startDate")
    end_date = request.args.get("endDate")
    category = request.args.get("category")
    sub_category = request.args.get("subCategory")
    limit = request.args.get("limit", 100, type=int)
    offset = request.args.get("offset", 0, type=int)

    account_ids, account_id_map = _get_account_ids_and_map(user_id)

    # Fetch Plaid transactions (if any linked accounts)
    all_txns = []
    if account_ids:
        # Lazy backfill: classify unclassified expense transactions
        all_txns, _ = get_transactions_for_accounts(account_ids, limit=10000)
        unclassified = [
            t for t in all_txns
            if (t.get('amount') or 0) > 0 and t.get('sub_category') in (None, 'unclassified')
        ]
        for txn in unclassified:
            classify_transaction(txn, user_id)

        # Re-fetch to get updated classification values
        all_txns, _ = get_transactions_for_accounts(
            account_ids, start_date=start_date, end_date=end_date, limit=10000
        )

    # Filter: expenses only (positive amount = money out)
    filtered = [t for t in all_txns if (t.get('amount') or 0) > 0]

    if category:
        filtered = [t for t in filtered if t.get('category_primary') == category]

    if sub_category:
        if sub_category == 'essential':
            filtered = [
                t for t in filtered
                if t.get('sub_category') == 'essential' or
                (t.get('sub_category') == 'mixed' and (t.get('essential_amount') or 0) > 0)
            ]
        elif sub_category == 'discretionary':
            filtered = [
                t for t in filtered
                if t.get('sub_category') == 'discretionary' or
                (t.get('sub_category') == 'mixed' and (t.get('discretionary_amount') or 0) > 0)
            ]
        else:
            filtered = [t for t in filtered if t.get('sub_category') == sub_category]

    # Compute summary
    total_essential = sum(
        (t.get('essential_amount') or 0) for t in filtered
        if t.get('sub_category') in ('essential', 'mixed')
    )
    total_discretionary = sum(
        (t.get('discretionary_amount') or 0) for t in filtered
        if t.get('sub_category') in ('discretionary', 'mixed')
    )
    total_unclassified = sum(
        (t.get('amount') or 0) for t in filtered
        if t.get('sub_category') in (None, 'unclassified')
    )

    total = len(filtered)
    paged = filtered[offset:offset + limit]

    result = []
    for txn in paged:
        result.append({
            "id": txn.key.id,
            "transactionId": txn.get('transaction_id'),
            "accountId": account_id_map.get(txn.get('plaid_account_id'), ''),
            "amount": txn.get('amount'),
            "date": txn.get('date'),
            "authorizedDate": txn.get('authorized_date'),
            "name": txn.get('name'),
            "merchantName": txn.get('merchant_name'),
            "categoryPrimary": txn.get('category_primary'),
            "categoryDetailed": txn.get('category_detailed'),
            "pending": txn.get('pending'),
            "paymentChannel": txn.get('payment_channel'),
            "subCategory": txn.get('sub_category') or 'unclassified',
            "essentialAmount": txn.get('essential_amount'),
            "discretionaryAmount": txn.get('discretionary_amount'),
        })

    # Merge in manual/voice-logged transactions
    manual_txns = get_manual_transactions(user_id)
    for mt in manual_txns:
        mt_date = mt.get('date') or ''
        # Apply date filters if set
        if start_date and mt_date < start_date:
            continue
        if end_date and mt_date > end_date:
            continue
        # Apply category filter if set
        if category and mt.get('category') != category:
            continue

        mt_amount = mt.get('amount') or 0
        mt_sub = mt.get('sub_category') or 'unclassified'
        mt_essential = mt.get('essential_amount')
        mt_discretionary = mt.get('discretionary_amount')

        # Apply sub_category filter if set
        if sub_category:
            if sub_category == 'essential' and mt_sub not in ('essential', 'mixed'):
                continue
            elif sub_category == 'discretionary' and mt_sub not in ('discretionary', 'mixed'):
                continue
            elif sub_category not in ('essential', 'discretionary') and mt_sub != sub_category:
                continue

        total += 1

        # Accumulate into summary totals
        if mt_sub == 'essential':
            total_essential += mt_essential or mt_amount
        elif mt_sub == 'discretionary':
            total_discretionary += mt_discretionary or mt_amount
        elif mt_sub == 'mixed':
            total_essential += mt_essential or 0
            total_discretionary += mt_discretionary or 0
        else:
            total_unclassified += mt_amount

        mt_source = mt.get('source') or 'manual'
        result.append({
            "id": mt.key.id,
            "transactionId": f"manual-{mt.key.id}",
            "accountId": "",
            "amount": mt_amount,
            "date": mt_date,
            "authorizedDate": mt_date,
            "name": mt.get('store') or mt.get('category') or 'Manual Transaction',
            "merchantName": mt.get('store'),
            "categoryPrimary": mt.get('category'),
            "categoryDetailed": mt.get('category'),
            "pending": False,
            "paymentChannel": mt_source,
            "subCategory": mt_sub,
            "essentialAmount": mt_essential,
            "discretionaryAmount": mt_discretionary,
            "source": mt_source,
        })

    # Sort all results by date descending
    result.sort(key=lambda t: t.get('date') or '', reverse=True)

    # Re-paginate after merging
    total = len(result)
    result = result[offset:offset + limit]

    return jsonify({
        "transactions": result,
        "summary": {
            "totalEssential": round(total_essential, 2),
            "totalDiscretionary": round(total_discretionary, 2),
            "totalFunMoney": round(total_discretionary, 2),
            "totalMixed": 0,
            "totalUnclassified": round(total_unclassified, 2),
        },
        "total": total,
        "hasMore": offset + limit < total,
    })


@expenses_bp.route("/merchant/classify", methods=["POST"])
def classify_merchant():
    """
    User classifies a merchant. Upserts MerchantClassification
    and retroactively reclassifies all past transactions for that merchant.
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    user_id = data.get("userId")
    merchant_name = data.get("merchantName")
    classification = data.get("classification")
    essential_ratio = data.get("essentialRatio")

    if not user_id or not merchant_name or not classification:
        return jsonify({"error": "userId, merchantName, and classification are required"}), 400

    if classification == 'split':
        classification = 'mixed'

    if classification not in ('essential', 'discretionary', 'mixed'):
        return jsonify({"error": "classification must be essential, discretionary, mixed, or split"}), 400

    if essential_ratio is None:
        if classification == 'essential':
            essential_ratio = 1.0
        elif classification == 'discretionary':
            essential_ratio = 0.0
        else:
            essential_ratio = 0.5

    normalized = normalize_merchant_name(merchant_name)
    user_id = int(user_id)

    mc = get_merchant_classification(user_id, normalized)
    upsert_merchant_classification(
        user_id, normalized,
        classification=classification,
        essential_ratio=essential_ratio,
        confidence='user_set',
        classification_count=(mc.get('classification_count') or 0) + 1 if mc else 1,
    )

    count = retroactively_reclassify(user_id, merchant_name, classification, essential_ratio)
    return jsonify({"success": True, "reclassifiedCount": count})


@expenses_bp.route("/transaction/<int:transaction_id>/classify", methods=["PUT"])
def classify_single_transaction(transaction_id):
    """
    User adjusts classification of a single transaction.
    Also updates the merchant's running average.
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    sub_category = data.get("subCategory")
    essential_ratio = data.get("essentialRatio")

    if sub_category == 'split':
        sub_category = 'mixed'

    if not sub_category or sub_category not in ('essential', 'discretionary', 'mixed'):
        return jsonify({"error": "subCategory must be essential, discretionary, mixed, or split"}), 400

    if essential_ratio is None:
        if sub_category == 'essential':
            essential_ratio = 1.0
        elif sub_category == 'discretionary':
            essential_ratio = 0.0
        else:
            essential_ratio = 0.5

    client = get_client()
    txn = client.get(client.key('Transaction', transaction_id))
    if not txn:
        return jsonify({"error": "Transaction not found"}), 404

    amount = abs(txn.get('amount') or 0.0)
    txn['sub_category'] = sub_category
    txn['essential_amount'] = round(amount * essential_ratio, 2)
    txn['discretionary_amount'] = round(amount * (1.0 - essential_ratio), 2)
    client.put(txn)

    # Update merchant running average and check auto-apply threshold
    updated_merchant_ratio = essential_ratio
    auto_applied = 0
    merchant = normalize_merchant_name(txn.get('merchant_name'))

    if merchant:
        # Traverse Transaction → PlaidAccount → PlaidItem to get user_id
        user_id = None
        plaid_account_id = txn.get('plaid_account_id')
        if plaid_account_id:
            account = client.get(client.key('PlaidAccount', plaid_account_id))
            if account:
                plaid_item_id = account.get('plaid_item_id')
                if plaid_item_id:
                    item = client.get(client.key('PlaidItem', plaid_item_id))
                    if item:
                        user_id = item.get('user_id')

        if user_id is not None:
            mc = get_merchant_classification(user_id, merchant)
            if mc:
                old_count = mc.get('classification_count') or 0
                new_count = old_count + 1
                new_ratio = round(
                    ((mc.get('essential_ratio', 0.5) * old_count) + essential_ratio) / new_count, 4
                )
                upsert_merchant_classification(
                    user_id, merchant,
                    classification=sub_category,
                    essential_ratio=new_ratio,
                    confidence='user_set',
                    classification_count=new_count,
                )
                updated_merchant_ratio = new_ratio
            else:
                upsert_merchant_classification(
                    user_id, merchant,
                    classification=sub_category,
                    essential_ratio=essential_ratio,
                    confidence='user_set',
                    classification_count=1,
                )

            # Re-fetch to check threshold
            mc = get_merchant_classification(user_id, merchant)
            if (mc and
                    (mc.get('classification_count') or 0) >= CONFIDENCE_THRESHOLD and
                    mc.get('confidence') == 'user_set'):
                auto_applied = retroactively_reclassify(
                    user_id, merchant, mc['classification'], mc['essential_ratio']
                )
                # Restore this transaction's exact user-set amounts
                txn['essential_amount'] = round(amount * essential_ratio, 2)
                txn['discretionary_amount'] = round(amount * (1.0 - essential_ratio), 2)
                client.put(txn)

    return jsonify({
        "success": True,
        "transaction": {
            "id": txn.key.id,
            "subCategory": txn.get('sub_category'),
            "essentialAmount": txn.get('essential_amount'),
            "discretionaryAmount": txn.get('discretionary_amount'),
        },
        "updatedMerchantRatio": updated_merchant_ratio,
        "autoApplied": auto_applied,
    })


@expenses_bp.route("/merchant/classifications/<int:user_id>", methods=["GET"])
def get_merchant_classifications(user_id):
    """Get all merchant classifications for a user."""
    user = get_user(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    classifications = get_merchant_classifications_for_user(user_id)
    return jsonify({
        "classifications": [
            {
                "merchantName": mc.get('merchant_name'),
                "classification": mc.get('classification'),
                "essentialRatio": mc.get('essential_ratio'),
                "confidence": mc.get('confidence'),
                "classificationCount": mc.get('classification_count'),
            }
            for mc in classifications
        ]
    })


@expenses_bp.route("/expenses/unclassified/<int:user_id>", methods=["GET"])
def get_unclassified_transactions(user_id):
    """Get individual unclassified transactions sorted by merchant impact, round-robin."""
    user = get_user(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    limit = request.args.get("limit", 10, type=int)

    account_ids, _ = _get_account_ids_and_map(user_id)
    if not account_ids:
        return jsonify({"transactions": [], "totalUnclassified": 0})

    all_txns, _ = get_transactions_for_accounts(account_ids, limit=10000)
    unclassified = [
        t for t in all_txns
        if (t.get('amount') or 0) > 0 and t.get('sub_category') in (None, 'unclassified')
    ]
    total_unclassified = len(unclassified)

    # Skip merchants where user has already reached the confidence threshold
    high_confidence_merchants = set()
    for mc in get_merchant_classifications_for_user(user_id):
        if (mc.get('classification_count') or 0) >= CONFIDENCE_THRESHOLD and mc.get('confidence') == 'user_set':
            high_confidence_merchants.add(mc.get('merchant_name', ''))

    # Group by merchant
    merchant_txns = {}
    for txn in unclassified:
        name = normalize_merchant_name(txn.get('merchant_name'))
        if name in high_confidence_merchants:
            continue
        if name not in merchant_txns:
            merchant_txns[name] = []
        merchant_txns[name].append(txn)

    # Sort merchants by total unclassified spend (highest first)
    sorted_merchants = sorted(
        merchant_txns.items(),
        key=lambda x: sum((t.get('amount') or 0) for t in x[1]),
        reverse=True,
    )

    # Within each merchant, sort by date descending
    for _, txns in sorted_merchants:
        txns.sort(key=lambda t: t.get('date') or '', reverse=True)

    # Build merchant context (total spend + classified/unclassified counts)
    merchant_context_data = {}
    for txn in all_txns:
        if (txn.get('amount') or 0) <= 0:
            continue
        name = normalize_merchant_name(txn.get('merchant_name'))
        if not name:
            continue
        if name not in merchant_context_data:
            merchant_context_data[name] = {"totalSpent": 0, "classified": 0, "unclassified": 0}
        merchant_context_data[name]["totalSpent"] += txn.get('amount') or 0
        if txn.get('sub_category') and txn.get('sub_category') != 'unclassified':
            merchant_context_data[name]["classified"] += 1
        else:
            merchant_context_data[name]["unclassified"] += 1

    # Round-robin: one transaction per merchant in order, repeat until limit
    result_txns = []
    pointers = {name: 0 for name, _ in sorted_merchants}

    while len(result_txns) < limit:
        added_any = False
        for name, txns in sorted_merchants:
            if pointers[name] < len(txns) and len(result_txns) < limit:
                txn = txns[pointers[name]]
                pointers[name] += 1
                added_any = True
                ctx = merchant_context_data.get(name, {})
                result_txns.append({
                    "id": txn.key.id,
                    "transactionId": txn.get('transaction_id'),
                    "merchantName": txn.get('merchant_name'),
                    "amount": txn.get('amount'),
                    "date": txn.get('date'),
                    "name": txn.get('name'),
                    "merchantContext": {
                        "totalUnclassified": ctx.get("unclassified", 0),
                        "totalSpent": round(ctx.get("totalSpent", 0), 2),
                        "alreadyClassified": ctx.get("classified", 0),
                    },
                })
        if not added_any:
            break

    return jsonify({"transactions": result_txns, "totalUnclassified": total_unclassified})


@expenses_bp.route("/expenses/auto-classify/<int:user_id>", methods=["POST"])
def auto_classify_with_llm(user_id):
    """
    Trigger LLM-based batch classification for unclassified merchants.
    Classifies up to 20 merchants at once using AI inference.
    """
    user = get_user(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    account_ids, _ = _get_account_ids_and_map(user_id)
    if not account_ids:
        return jsonify({"classified": 0, "merchants": []})

    all_txns, _ = get_transactions_for_accounts(account_ids, limit=10000)
    unclassified = [
        t for t in all_txns
        if (t.get('amount') or 0) > 0 and
        t.get('sub_category') in (None, 'unclassified') and
        t.get('merchant_name')
    ]

    merchant_info = {}
    for txn in unclassified:
        name = normalize_merchant_name(txn.get('merchant_name'))
        if not name or name in merchant_info:
            continue
        merchant_info[name] = {
            "name": txn.get('merchant_name'),
            "category_primary": txn.get('category_primary'),
            "category_detailed": txn.get('category_detailed'),
        }

    if not merchant_info:
        return jsonify({"classified": 0, "merchants": []})

    merchants_to_classify = list(merchant_info.values())[:20]
    results = llm_classify_merchants_batch(merchants_to_classify, user_id)

    classified_count = 0
    classified_merchants = []

    for result in results:
        merchant_name = result.get("name", "")
        classification = result["classification"]
        essential_ratio = result["essential_ratio"]
        normalized = normalize_merchant_name(merchant_name)

        if not normalized:
            continue

        if not get_merchant_classification(user_id, normalized):
            upsert_merchant_classification(
                user_id, normalized,
                classification=classification,
                essential_ratio=essential_ratio,
                confidence='inferred',
                classification_count=1,
            )

        count = retroactively_reclassify(user_id, merchant_name, classification, essential_ratio)
        classified_count += count
        classified_merchants.append({
            "merchantName": merchant_name,
            "classification": classification,
            "essentialRatio": essential_ratio,
            "transactionsUpdated": count,
        })

    return jsonify({"classified": classified_count, "merchants": classified_merchants})


@expenses_bp.route("/device/register", methods=["POST"])
def register_device_token():
    """Register a device token for push notifications."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    user_id = data.get("userId")
    token = data.get("token", "").strip()
    platform = data.get("platform", "ios")

    if not user_id or not token:
        return jsonify({"error": "userId and token are required"}), 400

    user = get_user(int(user_id))
    if not user:
        return jsonify({"error": "User not found"}), 404

    upsert_device_token(int(user_id), token, platform=platform, is_active=True)
    return jsonify({"success": True})


@expenses_bp.route("/device/unregister", methods=["POST"])
def unregister_device_token():
    """Unregister a device token (e.g., on logout)."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    user_id = data.get("userId")
    token = data.get("token", "").strip()

    if not user_id or not token:
        return jsonify({"error": "userId and token are required"}), 400

    existing = get_device_token(int(user_id), token)
    if existing:
        existing['is_active'] = False
        get_client().put(existing)

    return jsonify({"success": True})
