"""
Database helpers for BudgetBuddy using Google Cloud Datastore (Firestore in Datastore Mode).
Replaces the previous SQLAlchemy/SQLite implementation.

All helper functions return google.cloud.datastore.Entity objects.
Integer IDs are assigned automatically by Datastore and accessible via entity.key.id.
"""

import os
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from typing import Optional, List

from google.cloud import datastore
from google.cloud.datastore.query import PropertyFilter


def get_client() -> datastore.Client:
    """Return a Datastore client.

    When USE_LOCAL_DB is set to a truthy value, routes requests to the
    local Datastore emulator (localhost:8081) and skips authentication.
    Otherwise uses ADC / GOOGLE_APPLICATION_CREDENTIALS for production.
    """
    if os.environ.get("USE_LOCAL_DB", "").lower() in ("1", "true", "yes"):
        os.environ.setdefault("DATASTORE_EMULATOR_HOST", "localhost:8081")
        return datastore.Client(project="budgetbuddy-local")
    return datastore.Client()


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------

def get_user(user_id: str) -> Optional[datastore.Entity]:
    client = get_client()
    key = client.key('User', user_id)
    return client.get(key)


def get_user_by_firebase_uid(firebase_uid: str) -> Optional[datastore.Entity]:
    client = get_client()
    key = client.key('User', firebase_uid)
    return client.get(key)


def create_user(firebase_uid: str, phone: str = None, name: str = None) -> datastore.Entity:
    client = get_client()
    key = client.key('User', firebase_uid)
    entity = datastore.Entity(key=key)
    entity.update({
        'phone_number': phone,
        'name': name,
        'created_at': datetime.utcnow(),
    })
    client.put(entity)
    return entity


def update_user(user_id: str, **kwargs) -> bool:
    client = get_client()
    key = client.key('User', user_id)
    entity = client.get(key)
    if not entity:
        return False
    entity.update(kwargs)
    client.put(entity)
    return True


def delete_user_cascade(user_id: str):
    """Delete a user and all related Datastore entities."""
    client = get_client()
    _delete_kind_for_user(client, 'FinancialProfile', user_id)
    _delete_kind_for_user(client, 'BudgetPlan', user_id)
    _delete_kind_for_user(client, 'ManualTransaction', user_id)
    _delete_kind_for_user(client, 'CachedRecommendations', user_id)
    _delete_kind_for_user(client, 'DeviceToken', user_id)
    _delete_kind_for_user(client, 'MerchantClassification', user_id)
    _delete_kind_for_user(client, 'UserCategoryPreference', user_id)

    # Clean up OTP codes associated with user's phone
    user = client.get(client.key('User', user_id))
    if user and user.get('phone'):
        otp_query = client.query(kind='OTPCode')
        otp_query.add_filter(filter=PropertyFilter('phone', '=', user['phone']))
        otp_keys = [e.key for e in otp_query.fetch()]
        if otp_keys:
            client.delete_multi(otp_keys)

    statement = get_statement(user_id)
    if statement:
        client.delete(statement.key)

    for item in get_plaid_items(user_id):
        delete_plaid_item_cascade(item.key)

    _delete_kind_for_user(client, 'RecommendationPreferences', user_id)

    # Revoke Plaid access tokens before deleting
    _revoke_plaid_tokens_for_user(user_id)

    client.delete(client.key('User', user_id))


def _delete_kind_for_user(client: datastore.Client, kind: str, user_id: str):
    query = client.query(kind=kind)
    query.add_filter(filter=PropertyFilter('user_id', '=', user_id))
    keys = [e.key for e in query.fetch()]
    if keys:
        client.delete_multi(keys)


# ---------------------------------------------------------------------------
# OTPCode
# ---------------------------------------------------------------------------

def create_otp(phone: str, code: str, expires_at: datetime) -> datastore.Entity:
    client = get_client()
    key = client.key('OTPCode')
    entity = datastore.Entity(key=key)
    entity.update({
        'phone_number': phone,
        'code': code,
        'expires_at': expires_at,
        'verified': False,
        'created_at': datetime.utcnow(),
    })
    client.put(entity)
    return entity


def get_pending_otp(phone: str) -> Optional[datastore.Entity]:
    client = get_client()
    query = client.query(kind='OTPCode')
    query.add_filter(filter=PropertyFilter('phone_number', '=', phone))
    query.add_filter(filter=PropertyFilter('verified', '=', False))
    results = list(query.fetch())
    if not results:
        return None
    results.sort(key=lambda e: e.get('created_at', datetime.min), reverse=True)
    return results[0]


def mark_otp_verified(otp_key):
    client = get_client()
    entity = client.get(otp_key)
    if entity:
        entity['verified'] = True
        client.put(entity)


def delete_otps_for_phone(phone: str):
    client = get_client()
    query = client.query(kind='OTPCode')
    query.add_filter(filter=PropertyFilter('phone_number', '=', phone))
    keys = [e.key for e in query.fetch()]
    if keys:
        client.delete_multi(keys)


# ---------------------------------------------------------------------------
# FinancialProfile
# ---------------------------------------------------------------------------

def get_profile(user_id: int) -> Optional[datastore.Entity]:
    client = get_client()
    query = client.query(kind='FinancialProfile')
    query.add_filter(filter=PropertyFilter('user_id', '=', user_id))
    results = list(query.fetch(limit=1))
    return results[0] if results else None


def upsert_profile(user_id: int, **kwargs) -> datastore.Entity:
    client = get_client()
    existing = get_profile(user_id)
    if existing:
        entity = existing
    else:
        key = client.key('FinancialProfile')
        entity = datastore.Entity(key=key)
        entity['user_id'] = user_id
        entity['created_at'] = datetime.utcnow()
    entity.update(kwargs)
    client.put(entity)
    return entity


# ---------------------------------------------------------------------------
# BudgetPlan
# ---------------------------------------------------------------------------

def get_latest_plan(user_id: int) -> Optional[datastore.Entity]:
    client = get_client()
    query = client.query(kind='BudgetPlan')
    query.add_filter(filter=PropertyFilter('user_id', '=', user_id))
    results = list(query.fetch())
    if not results:
        return None
    results.sort(key=lambda e: e.get('created_at', datetime.min), reverse=True)
    return results[0]


def create_plan(user_id: int, plan_json: str, month_year: str) -> datastore.Entity:
    client = get_client()
    key = client.key('BudgetPlan')
    entity = datastore.Entity(key=key, exclude_from_indexes=['plan_json'])
    entity.update({
        'user_id': user_id,
        'plan_json': plan_json,
        'month_year': month_year,
        'created_at': datetime.utcnow(),
    })
    client.put(entity)
    return entity


# ---------------------------------------------------------------------------
# SavedStatement
# ---------------------------------------------------------------------------

def get_statement(user_id: int) -> Optional[datastore.Entity]:
    client = get_client()
    query = client.query(kind='SavedStatement')
    query.add_filter(filter=PropertyFilter('user_id', '=', user_id))
    results = list(query.fetch(limit=1))
    return results[0] if results else None


def upsert_statement(user_id: int, **kwargs) -> datastore.Entity:
    client = get_client()
    existing = get_statement(user_id)
    if existing:
        entity = existing
    else:
        key = client.key('SavedStatement')
        entity = datastore.Entity(key=key, exclude_from_indexes=['parsed_data', 'llm_analysis'])
        entity['user_id'] = user_id
        entity['created_at'] = datetime.utcnow()
    entity.update(kwargs)
    client.put(entity)
    return entity


def delete_statement_for_user(user_id: int):
    client = get_client()
    query = client.query(kind='SavedStatement')
    query.add_filter(filter=PropertyFilter('user_id', '=', user_id))
    keys = [e.key for e in query.fetch()]
    if keys:
        client.delete_multi(keys)


# ---------------------------------------------------------------------------
# PlaidItem
# ---------------------------------------------------------------------------

def get_plaid_items(user_id: int) -> List[datastore.Entity]:
    client = get_client()
    query = client.query(kind='PlaidItem')
    query.add_filter(filter=PropertyFilter('user_id', '=', user_id))
    return list(query.fetch())


def get_active_plaid_items(user_id: int) -> List[datastore.Entity]:
    client = get_client()
    query = client.query(kind='PlaidItem')
    query.add_filter(filter=PropertyFilter('user_id', '=', user_id))
    query.add_filter(filter=PropertyFilter('status', '=', 'active'))
    return list(query.fetch())


def create_plaid_item(user_id: int, **kwargs) -> datastore.Entity:
    client = get_client()
    key = client.key('PlaidItem')
    entity = datastore.Entity(key=key, exclude_from_indexes=['access_token_encrypted'])
    entity['user_id'] = user_id
    entity['created_at'] = datetime.utcnow()
    entity.update(kwargs)
    client.put(entity)
    return entity


def get_plaid_item_by_item_id(item_id: str) -> Optional[datastore.Entity]:
    client = get_client()
    query = client.query(kind='PlaidItem')
    query.add_filter(filter=PropertyFilter('item_id', '=', item_id))
    results = list(query.fetch(limit=1))
    return results[0] if results else None


def update_plaid_item(key, **kwargs):
    client = get_client()
    entity = client.get(key)
    if entity:
        entity.update(kwargs)
        client.put(entity)


def delete_plaid_item_cascade(item_key):
    """Delete a PlaidItem and all its accounts + transactions."""
    client = get_client()
    plaid_item_id = item_key.id
    for account in get_accounts_for_item(plaid_item_id):
        txn_query = client.query(kind='Transaction')
        txn_query.add_filter(filter=PropertyFilter('plaid_account_id', '=', account.key.id))
        txn_keys = [e.key for e in txn_query.fetch()]
        if txn_keys:
            client.delete_multi(txn_keys)
        client.delete(account.key)
    client.delete(item_key)


# ---------------------------------------------------------------------------
# PlaidAccount
# ---------------------------------------------------------------------------

def get_accounts_for_item(plaid_item_id: int) -> List[datastore.Entity]:
    client = get_client()
    query = client.query(kind='PlaidAccount')
    query.add_filter(filter=PropertyFilter('plaid_item_id', '=', plaid_item_id))
    return list(query.fetch())


def create_plaid_account(plaid_item_id: int, **kwargs) -> datastore.Entity:
    client = get_client()
    key = client.key('PlaidAccount')
    entity = datastore.Entity(key=key)
    entity['plaid_item_id'] = plaid_item_id
    entity['created_at'] = datetime.utcnow()
    entity.update(kwargs)
    client.put(entity)
    return entity


def get_account_by_account_id(account_id: str) -> Optional[datastore.Entity]:
    client = get_client()
    query = client.query(kind='PlaidAccount')
    query.add_filter(filter=PropertyFilter('account_id', '=', account_id))
    results = list(query.fetch(limit=1))
    return results[0] if results else None


# ---------------------------------------------------------------------------
# Transaction
# ---------------------------------------------------------------------------

def create_transaction(plaid_account_id: int, **kwargs) -> datastore.Entity:
    client = get_client()
    key = client.key('Transaction')
    entity = datastore.Entity(key=key)
    entity['plaid_account_id'] = plaid_account_id
    entity['created_at'] = datetime.utcnow()
    entity.update(kwargs)
    client.put(entity)
    return entity


def get_transaction_by_transaction_id(txn_id: str) -> Optional[datastore.Entity]:
    client = get_client()
    query = client.query(kind='Transaction')
    query.add_filter(filter=PropertyFilter('transaction_id', '=', txn_id))
    results = list(query.fetch(limit=1))
    return results[0] if results else None


def get_transactions_for_accounts(
    account_ids: List[int],
    start_date=None,
    end_date=None,
    limit: int = 100,
    offset: int = 0,
):
    """
    Returns (transactions_page, total_count).
    Dates can be date/datetime objects or ISO strings.
    """
    client = get_client()
    all_txns = []
    for account_id in account_ids:
        query = client.query(kind='Transaction')
        query.add_filter(filter=PropertyFilter('plaid_account_id', '=', account_id))
        all_txns.extend(list(query.fetch()))

    if start_date:
        start_str = start_date if isinstance(start_date, str) else start_date.isoformat()
        all_txns = [t for t in all_txns if (t.get('date') or '') >= start_str]
    if end_date:
        end_str = end_date if isinstance(end_date, str) else end_date.isoformat()
        all_txns = [t for t in all_txns if (t.get('date') or '') <= end_str]

    all_txns.sort(key=lambda t: t.get('date', ''), reverse=True)
    total = len(all_txns)
    return all_txns[offset:offset + limit], total


def get_transactions_since(account_ids: List[int], since_date) -> List[datastore.Entity]:
    """Return all transactions for the given accounts on or after since_date."""
    client = get_client()
    all_txns = []
    for account_id in account_ids:
        query = client.query(kind='Transaction')
        query.add_filter(filter=PropertyFilter('plaid_account_id', '=', account_id))
        all_txns.extend(list(query.fetch()))

    since_str = since_date if isinstance(since_date, str) else since_date.isoformat()
    return [t for t in all_txns if (t.get('date') or '') >= since_str]


def update_transaction_by_id(txn_id: str, **kwargs):
    txn = get_transaction_by_transaction_id(txn_id)
    if txn:
        client = get_client()
        txn.update(kwargs)
        client.put(txn)


def delete_transaction_by_id(txn_id: str):
    txn = get_transaction_by_transaction_id(txn_id)
    if txn:
        get_client().delete(txn.key)


# ---------------------------------------------------------------------------
# UserCategoryPreference
# ---------------------------------------------------------------------------

def get_category_prefs(user_id: int) -> List[datastore.Entity]:
    client = get_client()
    query = client.query(kind='UserCategoryPreference')
    query.add_filter(filter=PropertyFilter('user_id', '=', user_id))
    results = list(query.fetch())
    results.sort(key=lambda e: e.get('display_order', 0))
    return results


def set_category_prefs(user_id: int, categories: list):
    """
    Replace all category preferences for a user.

    Each item in `categories` can be either:
    - A plain string (backward compatible): just the category name.
    - A dict with keys: name, emoji (optional), isBuiltin (optional).
    """
    client = get_client()
    query = client.query(kind='UserCategoryPreference')
    query.add_filter(filter=PropertyFilter('user_id', '=', user_id))
    keys = [e.key for e in query.fetch()]
    if keys:
        client.delete_multi(keys)
    for i, cat in enumerate(categories):
        key = client.key('UserCategoryPreference')
        entity = datastore.Entity(key=key)
        if isinstance(cat, dict):
            entity.update({
                'user_id': user_id,
                'category_name': cat.get('name', ''),
                'emoji': cat.get('emoji'),
                'is_builtin': cat.get('isBuiltin', True),
                'display_order': i,
                'weekly_limit': cat.get('weeklyLimit'),
                'created_at': datetime.utcnow(),
            })
        else:
            entity.update({
                'user_id': user_id,
                'category_name': cat,
                'display_order': i,
                'created_at': datetime.utcnow(),
            })
        client.put(entity)


def get_user_custom_categories(user_id: int) -> List[str]:
    """Return just the custom (non-builtin) category names for a user."""
    prefs = get_category_prefs(user_id)
    return [p.get('category_name') for p in prefs if p.get('is_builtin') is False]


# ---------------------------------------------------------------------------
# ManualTransaction (voice-logged)
# ---------------------------------------------------------------------------

def create_manual_transaction(user_id: int, **kwargs) -> datastore.Entity:
    client = get_client()
    key = client.key('ManualTransaction')
    entity = datastore.Entity(key=key)
    entity['user_id'] = user_id
    entity['created_at'] = datetime.utcnow()
    entity.update(kwargs)
    client.put(entity)
    return entity


def get_manual_transactions(user_id: int, limit: int = 0) -> List[datastore.Entity]:
    """Returns manual transactions for a user, sorted newest-first.
    limit=0 means no limit (return all)."""
    client = get_client()
    query = client.query(kind='ManualTransaction')
    query.add_filter(filter=PropertyFilter('user_id', '=', user_id))
    results = list(query.fetch())
    results.sort(key=lambda e: e.get('created_at', datetime.min), reverse=True)
    return results if limit == 0 else results[:limit]


def update_manual_transaction(txn_id: int, **kwargs) -> Optional[datastore.Entity]:
    client = get_client()
    entity = client.get(client.key('ManualTransaction', txn_id))
    if not entity:
        return None
    entity.update(kwargs)
    client.put(entity)
    return entity


# ---------------------------------------------------------------------------
# MerchantClassification
# ---------------------------------------------------------------------------

def get_merchant_classification(user_id: int, merchant_name: str) -> Optional[datastore.Entity]:
    client = get_client()
    query = client.query(kind='MerchantClassification')
    query.add_filter(filter=PropertyFilter('user_id', '=', user_id))
    query.add_filter(filter=PropertyFilter('merchant_name', '=', merchant_name))
    results = list(query.fetch(limit=1))
    return results[0] if results else None


def get_merchant_classifications_for_user(user_id: int) -> List[datastore.Entity]:
    client = get_client()
    query = client.query(kind='MerchantClassification')
    query.add_filter(filter=PropertyFilter('user_id', '=', user_id))
    return list(query.fetch())


def upsert_merchant_classification(user_id: int, merchant_name: str, **kwargs) -> datastore.Entity:
    client = get_client()
    existing = get_merchant_classification(user_id, merchant_name)
    if existing:
        entity = existing
    else:
        key = client.key('MerchantClassification')
        entity = datastore.Entity(key=key)
        entity['user_id'] = user_id
        entity['merchant_name'] = merchant_name
        entity['created_at'] = datetime.utcnow()
    entity.update(kwargs)
    client.put(entity)
    return entity


# ---------------------------------------------------------------------------
# DeviceToken
# ---------------------------------------------------------------------------

def get_active_device_tokens(user_id: int) -> List[datastore.Entity]:
    client = get_client()
    query = client.query(kind='DeviceToken')
    query.add_filter(filter=PropertyFilter('user_id', '=', user_id))
    query.add_filter(filter=PropertyFilter('is_active', '=', True))
    return list(query.fetch())


def get_device_token(user_id: int, token: str) -> Optional[datastore.Entity]:
    client = get_client()
    query = client.query(kind='DeviceToken')
    query.add_filter(filter=PropertyFilter('user_id', '=', user_id))
    query.add_filter(filter=PropertyFilter('token', '=', token))
    results = list(query.fetch(limit=1))
    return results[0] if results else None


def upsert_device_token(user_id: int, token: str, **kwargs) -> datastore.Entity:
    client = get_client()
    existing = get_device_token(user_id, token)
    if existing:
        entity = existing
    else:
        key = client.key('DeviceToken')
        entity = datastore.Entity(key=key)
        entity['user_id'] = user_id
        entity['token'] = token
        entity['created_at'] = datetime.utcnow()
    entity.update(kwargs)
    client.put(entity)
    return entity


# ---------------------------------------------------------------------------
# RecommendationPreferences (saved/disliked tips)
# ---------------------------------------------------------------------------

def get_recommendation_prefs(user_id: str) -> Optional[datastore.Entity]:
    client = get_client()
    query = client.query(kind='RecommendationPreferences')
    query.add_filter(filter=PropertyFilter('user_id', '=', user_id))
    results = list(query.fetch(limit=1))
    return results[0] if results else None


def upsert_recommendation_prefs(user_id: str, **kwargs) -> datastore.Entity:
    client = get_client()
    existing = get_recommendation_prefs(user_id)
    if existing:
        entity = existing
    else:
        key = client.key('RecommendationPreferences')
        entity = datastore.Entity(key=key, exclude_from_indexes=['saved_tips_json', 'disliked_tip_ids_json'])
        entity['user_id'] = user_id
        entity['created_at'] = datetime.utcnow()
    entity.update(kwargs)
    entity['updated_at'] = datetime.utcnow()
    client.put(entity)
    return entity


# ---------------------------------------------------------------------------
# CachedRecommendations
# ---------------------------------------------------------------------------

def get_cached_recommendations(user_id: int) -> Optional[datastore.Entity]:
    client = get_client()
    query = client.query(kind='CachedRecommendations')
    query.add_filter(filter=PropertyFilter('user_id', '=', user_id))
    results = list(query.fetch(limit=1))
    return results[0] if results else None


def upsert_cached_recommendations(user_id: int, **kwargs) -> datastore.Entity:
    client = get_client()
    existing = get_cached_recommendations(user_id)
    if existing:
        entity = existing
    else:
        key = client.key('CachedRecommendations')
        entity = datastore.Entity(key=key, exclude_from_indexes=['recommendations_json'])
        entity['user_id'] = user_id
        entity['created_at'] = datetime.utcnow()
    entity.update(kwargs)
    entity['updated_at'] = datetime.utcnow()
    client.put(entity)
    return entity


# ---------------------------------------------------------------------------
# Receipt helpers
# ---------------------------------------------------------------------------

def find_matching_transaction(
    user_id: int,
    amount: float,
    date_str: str,
    merchant: str,
) -> Optional[datastore.Entity]:
    """
    Find an existing Plaid Transaction that matches a receipt by amount (±$2),
    date (±2 days), and merchant name similarity (≥ 0.7).
    Returns the best match or None.
    """
    try:
        receipt_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None

    account_ids = []
    for item in get_plaid_items(user_id):
        for account in get_accounts_for_item(item.key.id):
            account_ids.append(account.key.id)

    if not account_ids:
        return None

    date_min = (receipt_date - timedelta(days=2)).isoformat()
    date_max = (receipt_date + timedelta(days=2)).isoformat()

    client = get_client()
    best_match = None
    best_score = 0.0

    for account_id in account_ids:
        query = client.query(kind='Transaction')
        query.add_filter(filter=PropertyFilter('plaid_account_id', '=', account_id))
        for txn in query.fetch():
            txn_date = txn.get('date') or ''
            if not (date_min <= txn_date <= date_max):
                continue
            txn_amount = abs(txn.get('amount') or 0.0)
            if abs(txn_amount - abs(amount)) > 2.0:
                continue
            txn_merchant = (txn.get('merchant_name') or txn.get('name') or '').lower().strip()
            merchant_norm = (merchant or '').lower().strip()
            if txn_merchant and merchant_norm:
                score = SequenceMatcher(None, txn_merchant, merchant_norm).ratio()
                if score >= 0.7 and score > best_score:
                    best_score = score
                    best_match = txn

    return best_match


def update_transaction_receipt(
    txn_id: int,
    receipt_items_json: str,
    essential_amount: float,
    discretionary_amount: float,
    sub_category: str,
    image_url: Optional[str] = None,
) -> Optional[datastore.Entity]:
    """Enrich an existing Plaid Transaction with receipt data."""
    client = get_client()
    entity = client.get(client.key('Transaction', txn_id))
    if not entity:
        return None
    entity['receipt_items'] = receipt_items_json
    entity['essential_amount'] = essential_amount
    entity['discretionary_amount'] = discretionary_amount
    entity['sub_category'] = sub_category
    if image_url:
        entity['receipt_image_url'] = image_url
    client.put(entity)
    return entity


def find_pending_receipt_transaction(
    user_id: int,
    amount: float,
    date_str: str,
    merchant: str,
) -> Optional[datastore.Entity]:
    """
    Find a ManualTransaction with pending_plaid_reconcile=True that matches
    the given Plaid transaction (amount ±$2, date ±2 days, merchant similarity ≥ 0.7).
    """
    try:
        plaid_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None

    client = get_client()
    query = client.query(kind='ManualTransaction')
    query.add_filter(filter=PropertyFilter('user_id', '=', user_id))
    query.add_filter(filter=PropertyFilter('pending_plaid_reconcile', '=', True))

    date_min = (plaid_date - timedelta(days=2)).isoformat()
    date_max = (plaid_date + timedelta(days=2)).isoformat()
    merchant_norm = (merchant or '').lower().strip()

    best_match = None
    best_score = 0.0

    for mt in query.fetch():
        mt_date = mt.get('date') or ''
        if not (date_min <= mt_date <= date_max):
            continue
        mt_amount = abs(mt.get('amount') or 0.0)
        if abs(mt_amount - abs(amount)) > 2.0:
            continue
        mt_merchant = (mt.get('store') or mt.get('notes') or '').lower().strip()
        if merchant_norm and mt_merchant:
            score = SequenceMatcher(None, mt_merchant, merchant_norm).ratio()
            if score >= 0.7 and score > best_score:
                best_score = score
                best_match = mt
        elif abs(mt_amount - abs(amount)) <= 2.0:
            # No merchant name to compare — match on amount+date alone
            if best_score == 0.0:
                best_match = mt

    return best_match


def reconcile_manual_with_plaid(manual_id: int, plaid_data: dict) -> Optional[datastore.Entity]:
    """
    Copy Plaid metadata into a ManualTransaction and clear the pending reconcile flag.
    """
    client = get_client()
    entity = client.get(client.key('ManualTransaction', manual_id))
    if not entity:
        return None
    entity['plaid_transaction_id'] = plaid_data.get('transaction_id')
    entity['merchant_name'] = plaid_data.get('merchant_name')
    entity['category_primary'] = plaid_data.get('category')
    entity['category_detailed'] = plaid_data.get('category_detailed')
    entity['payment_channel'] = plaid_data.get('payment_channel')
    entity['pending_plaid_reconcile'] = False
    client.put(entity)
    return entity
