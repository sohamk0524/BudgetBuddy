"""
Database helpers for BudgetBuddy using Google Cloud Datastore (Firestore in Datastore Mode).
Replaces the previous SQLAlchemy/SQLite implementation.

All helper functions return google.cloud.datastore.Entity objects.
Integer IDs are assigned automatically by Datastore and accessible via entity.key.id.
"""

import os
from datetime import datetime
from typing import Optional, List

from google.cloud import datastore


def get_client() -> datastore.Client:
    """Return a Datastore client (uses ADC or GOOGLE_APPLICATION_CREDENTIALS)."""
    return datastore.Client()


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------

def get_user(user_id: int) -> Optional[datastore.Entity]:
    client = get_client()
    key = client.key('User', user_id)
    return client.get(key)


def get_user_by_phone(phone: str) -> Optional[datastore.Entity]:
    client = get_client()
    query = client.query(kind='User')
    query.add_filter('phone_number', '=', phone)
    results = list(query.fetch(limit=1))
    return results[0] if results else None


def create_user(phone: str, name: str = None) -> datastore.Entity:
    client = get_client()
    key = client.key('User')
    entity = datastore.Entity(key=key)
    entity.update({
        'phone_number': phone,
        'name': name,
        'created_at': datetime.utcnow(),
    })
    client.put(entity)
    return entity


def update_user(user_id: int, **kwargs) -> bool:
    client = get_client()
    key = client.key('User', user_id)
    entity = client.get(key)
    if not entity:
        return False
    entity.update(kwargs)
    client.put(entity)
    return True


def delete_user_cascade(user_id: int):
    """Delete a user and all related Datastore entities."""
    client = get_client()
    user = get_user(user_id)
    if user:
        delete_otps_for_phone(user['phone_number'])

    _delete_kind_for_user(client, 'FinancialProfile', user_id)
    _delete_kind_for_user(client, 'BudgetPlan', user_id)

    statement = get_statement(user_id)
    if statement:
        client.delete(statement.key)

    for item in get_plaid_items(user_id):
        delete_plaid_item_cascade(item.key)

    _delete_kind_for_user(client, 'UserCategoryPreference', user_id)
    client.delete(client.key('User', user_id))


def _delete_kind_for_user(client: datastore.Client, kind: str, user_id: int):
    query = client.query(kind=kind)
    query.add_filter('user_id', '=', user_id)
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
    query.add_filter('phone_number', '=', phone)
    query.add_filter('verified', '=', False)
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
    query.add_filter('phone_number', '=', phone)
    keys = [e.key for e in query.fetch()]
    if keys:
        client.delete_multi(keys)


# ---------------------------------------------------------------------------
# FinancialProfile
# ---------------------------------------------------------------------------

def get_profile(user_id: int) -> Optional[datastore.Entity]:
    client = get_client()
    query = client.query(kind='FinancialProfile')
    query.add_filter('user_id', '=', user_id)
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
    query.add_filter('user_id', '=', user_id)
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
    query.add_filter('user_id', '=', user_id)
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
    query.add_filter('user_id', '=', user_id)
    keys = [e.key for e in query.fetch()]
    if keys:
        client.delete_multi(keys)


# ---------------------------------------------------------------------------
# PlaidItem
# ---------------------------------------------------------------------------

def get_plaid_items(user_id: int) -> List[datastore.Entity]:
    client = get_client()
    query = client.query(kind='PlaidItem')
    query.add_filter('user_id', '=', user_id)
    return list(query.fetch())


def get_active_plaid_items(user_id: int) -> List[datastore.Entity]:
    client = get_client()
    query = client.query(kind='PlaidItem')
    query.add_filter('user_id', '=', user_id)
    query.add_filter('status', '=', 'active')
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
    query.add_filter('item_id', '=', item_id)
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
        txn_query.add_filter('plaid_account_id', '=', account.key.id)
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
    query.add_filter('plaid_item_id', '=', plaid_item_id)
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
    query.add_filter('account_id', '=', account_id)
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
    query.add_filter('transaction_id', '=', txn_id)
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
        query.add_filter('plaid_account_id', '=', account_id)
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
        query.add_filter('plaid_account_id', '=', account_id)
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
    query.add_filter('user_id', '=', user_id)
    results = list(query.fetch())
    results.sort(key=lambda e: e.get('display_order', 0))
    return results


def set_category_prefs(user_id: int, categories: List[str]):
    client = get_client()
    query = client.query(kind='UserCategoryPreference')
    query.add_filter('user_id', '=', user_id)
    keys = [e.key for e in query.fetch()]
    if keys:
        client.delete_multi(keys)
    for i, cat_name in enumerate(categories):
        key = client.key('UserCategoryPreference')
        entity = datastore.Entity(key=key)
        entity.update({
            'user_id': user_id,
            'category_name': cat_name,
            'display_order': i,
            'created_at': datetime.utcnow(),
        })
        client.put(entity)


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


def get_manual_transactions(user_id: int, limit: int = 50) -> List[datastore.Entity]:
    client = get_client()
    query = client.query(kind='ManualTransaction')
    query.add_filter('user_id', '=', user_id)
    results = list(query.fetch())
    results.sort(key=lambda e: e.get('created_at', datetime.min), reverse=True)
    return results[:limit]
