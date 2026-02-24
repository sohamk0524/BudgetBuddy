"""
Plaid Blueprint — link token, exchange token, accounts, transactions, sync, unlink.
"""

from datetime import datetime

from flask import Blueprint, jsonify, request

from db_models import (
    get_user,
    get_plaid_items,
    get_active_plaid_items,
    get_accounts_for_item,
    create_plaid_item,
    create_plaid_account,
    create_transaction,
    get_transaction_by_transaction_id,
    update_transaction_by_id,
    delete_transaction_by_id,
    get_plaid_item_by_item_id,
    update_plaid_item,
    delete_plaid_item_cascade,
    get_transactions_for_accounts,
)
from services import plaid_service

plaid_bp = Blueprint('plaid', __name__)


def _parse_date(date_str):
    """Parse YYYY-MM-DD string to date, return None on failure."""
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


@plaid_bp.route("/plaid/link-token", methods=["POST"])
def create_plaid_link_token():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    user_id = data.get("userId")
    if not user_id:
        return jsonify({"error": "userId is required"}), 400

    user = get_user(int(user_id))
    if not user:
        return jsonify({"error": "User not found"}), 404

    try:
        result = plaid_service.create_link_token(user_id)
        return jsonify({
            "linkToken": result["link_token"],
            "expiration": result["expiration"],
        })
    except ValueError as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        print(f"Plaid link token error: {e}")
        return jsonify({"error": "Failed to create link token"}), 500


@plaid_bp.route("/plaid/exchange-token", methods=["POST"])
def exchange_plaid_token():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    user_id = data.get("userId")
    public_token = data.get("publicToken")
    institution_id = data.get("institutionId")
    institution_name = data.get("institutionName")

    if not user_id or not public_token:
        return jsonify({"error": "userId and publicToken are required"}), 400

    user = get_user(int(user_id))
    if not user:
        return jsonify({"error": "User not found"}), 404

    try:
        encrypted_token, item_id = plaid_service.exchange_public_token(public_token)

        plaid_item = create_plaid_item(
            int(user_id),
            item_id=item_id,
            access_token_encrypted=encrypted_token,
            institution_id=institution_id,
            institution_name=institution_name or plaid_service.get_institution_name(institution_id),
            status="active",
        )
        plaid_item_id = plaid_item.key.id

        accounts_response = plaid_service.get_accounts(encrypted_token)
        account_records = []

        for account_data in accounts_response["accounts"]:
            account = create_plaid_account(
                plaid_item_id,
                account_id=account_data["account_id"],
                name=account_data["name"],
                official_name=account_data["official_name"],
                account_type=account_data["type"],
                account_subtype=account_data["subtype"],
                balance_available=account_data["balances"]["available"],
                balance_current=account_data["balances"]["current"],
                balance_limit=account_data["balances"]["limit"],
                mask=account_data["mask"],
            )
            account_records.append(account)

        # Build Plaid account_id → our PlaidAccount entity map
        account_map = {acc['account_id']: acc for acc in account_records}

        transactions = plaid_service.fetch_historical_transactions(encrypted_token, months=6)
        transaction_count = 0
        for txn_data in transactions:
            account = account_map.get(txn_data["account_id"])
            if account:
                create_transaction(
                    account.key.id,
                    transaction_id=txn_data["transaction_id"],
                    amount=txn_data["amount"],
                    date=txn_data["date"],
                    authorized_date=txn_data["authorized_date"],
                    name=txn_data["name"],
                    merchant_name=txn_data["merchant_name"],
                    category_primary=txn_data["category"],
                    category_detailed=txn_data["category_detailed"],
                    category_confidence=txn_data["category_confidence"],
                    pending=txn_data["pending"],
                    payment_channel=txn_data["payment_channel"],
                )
                transaction_count += 1

        return jsonify({
            "success": True,
            "itemId": item_id,
            "accounts": [
                {
                    "accountId": acc['account_id'],
                    "name": acc['name'],
                    "type": acc['account_type'],
                    "subtype": acc['account_subtype'],
                    "mask": acc.get('mask'),
                    "balanceCurrent": acc.get('balance_current'),
                    "balanceAvailable": acc.get('balance_available'),
                }
                for acc in account_records
            ],
            "transactionCount": transaction_count,
        })

    except ValueError as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        print(f"Plaid exchange token error: {e}")
        return jsonify({"error": "Failed to exchange token and fetch data"}), 500


@plaid_bp.route("/plaid/accounts/<int:user_id>", methods=["GET"])
def get_plaid_accounts(user_id):
    user = get_user(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    items = get_plaid_items(user_id)
    result = []
    for item in items:
        accounts = []
        for account in get_accounts_for_item(item.key.id):
            accounts.append({
                "accountId": account.get('account_id'),
                "name": account.get('name'),
                "officialName": account.get('official_name'),
                "type": account.get('account_type'),
                "subtype": account.get('account_subtype'),
                "mask": account.get('mask'),
                "balanceAvailable": account.get('balance_available'),
                "balanceCurrent": account.get('balance_current'),
                "balanceLimit": account.get('balance_limit'),
            })

        created_at = item.get('created_at')
        result.append({
            "itemId": item.get('item_id'),
            "institutionId": item.get('institution_id'),
            "institutionName": item.get('institution_name'),
            "status": item.get('status'),
            "createdAt": created_at.isoformat() if created_at else None,
            "accounts": accounts,
        })

    return jsonify({"items": result})


@plaid_bp.route("/plaid/transactions/<int:user_id>", methods=["GET"])
def get_plaid_transactions(user_id):
    user = get_user(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    start_date = request.args.get("startDate")
    end_date = request.args.get("endDate")
    limit = request.args.get("limit", 100, type=int)
    offset = request.args.get("offset", 0, type=int)

    # Gather all internal account IDs and build account_id lookup
    plaid_items = get_plaid_items(user_id)
    account_ids = []
    account_id_map = {}  # internal key.id → Plaid account_id string
    for item in plaid_items:
        for account in get_accounts_for_item(item.key.id):
            account_ids.append(account.key.id)
            account_id_map[account.key.id] = account['account_id']

    if not account_ids:
        return jsonify({"transactions": [], "total": 0, "hasMore": False})

    transactions, total = get_transactions_for_accounts(
        account_ids,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=offset,
    )

    result = []
    for txn in transactions:
        result.append({
            "transactionId": txn.get('transaction_id'),
            "accountId": account_id_map.get(txn.get('plaid_account_id'), ""),
            "amount": txn.get('amount'),
            "date": txn.get('date'),
            "authorizedDate": txn.get('authorized_date'),
            "name": txn.get('name'),
            "merchantName": txn.get('merchant_name'),
            "categoryPrimary": txn.get('category_primary'),
            "categoryDetailed": txn.get('category_detailed'),
            "pending": txn.get('pending'),
            "paymentChannel": txn.get('payment_channel'),
        })

    return jsonify({
        "transactions": result,
        "total": total,
        "hasMore": offset + limit < total,
    })


@plaid_bp.route("/plaid/sync/<int:user_id>", methods=["POST"])
def sync_plaid_transactions(user_id):
    user = get_user(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    plaid_items = get_active_plaid_items(user_id)
    if not plaid_items:
        return jsonify({"error": "No linked accounts found"}), 404

    total_added = 0
    total_modified = 0
    total_removed = 0

    for item in plaid_items:
        try:
            account_map = {
                acc['account_id']: acc
                for acc in get_accounts_for_item(item.key.id)
            }
            has_more = True
            cursor = item.get('transactions_cursor')

            while has_more:
                result = plaid_service.sync_transactions(
                    item['access_token_encrypted'],
                    cursor,
                )

                for txn_data in result["added"]:
                    account = account_map.get(txn_data["account_id"])
                    if account:
                        existing = get_transaction_by_transaction_id(txn_data["transaction_id"])
                        if not existing:
                            create_transaction(
                                account.key.id,
                                transaction_id=txn_data["transaction_id"],
                                amount=txn_data["amount"],
                                date=txn_data["date"],
                                authorized_date=txn_data["authorized_date"],
                                name=txn_data["name"],
                                merchant_name=txn_data["merchant_name"],
                                category_primary=txn_data["category"],
                                category_detailed=txn_data["category_detailed"],
                                category_confidence=txn_data["category_confidence"],
                                pending=txn_data["pending"],
                                payment_channel=txn_data["payment_channel"],
                            )
                            total_added += 1

                for txn_data in result["modified"]:
                    update_transaction_by_id(
                        txn_data["transaction_id"],
                        amount=txn_data["amount"],
                        date=txn_data["date"],
                        name=txn_data["name"],
                        merchant_name=txn_data["merchant_name"],
                        category_primary=txn_data["category"],
                        category_detailed=txn_data["category_detailed"],
                        pending=txn_data["pending"],
                    )
                    total_modified += 1

                for removed in result["removed"]:
                    delete_transaction_by_id(removed["transaction_id"])
                    total_removed += 1

                cursor = result["next_cursor"]
                has_more = result["has_more"]

            update_plaid_item(item.key, transactions_cursor=cursor)

        except Exception as e:
            print(f"Error syncing item {item.get('item_id')}: {e}")
            continue

    return jsonify({
        "added": total_added,
        "modified": total_modified,
        "removed": total_removed,
    })


@plaid_bp.route("/plaid/unlink/<int:user_id>/<item_id>", methods=["DELETE"])
def unlink_plaid_item(user_id, item_id):
    user = get_user(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    plaid_item = get_plaid_item_by_item_id(item_id)
    if not plaid_item or plaid_item.get('user_id') != user_id:
        return jsonify({"error": "Plaid item not found"}), 404

    try:
        plaid_service.remove_item(plaid_item['access_token_encrypted'])
    except Exception as e:
        print(f"Warning: Failed to remove item from Plaid: {e}")

    delete_plaid_item_cascade(plaid_item.key)

    return jsonify({"success": True})
