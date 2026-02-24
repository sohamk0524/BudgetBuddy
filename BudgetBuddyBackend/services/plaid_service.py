"""
Plaid API integration service for BudgetBuddy.
Handles all interactions with the Plaid API including Link flow,
account fetching, and transaction syncing.
"""

import os
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple

import plaid
from plaid.api import plaid_api
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from plaid.model.accounts_get_request import AccountsGetRequest
from plaid.model.transactions_sync_request import TransactionsSyncRequest
from plaid.model.transactions_get_request import TransactionsGetRequest
from plaid.model.transactions_get_request_options import TransactionsGetRequestOptions
from plaid.model.item_remove_request import ItemRemoveRequest
from plaid.model.products import Products
from plaid.model.country_code import CountryCode

from services.encryption_service import encrypt_token, decrypt_token


def _get_enum_value(obj) -> Optional[str]:
    """Safely extract value from enum or return string directly."""
    if obj is None:
        return None
    if hasattr(obj, 'value'):
        return obj.value
    return str(obj)


def _get_plaid_host() -> str:
    """Get the Plaid API host URL from environment variable."""
    env = os.environ.get("PLAID_ENV", "sandbox").lower()
    env_map = {
        "sandbox": "https://sandbox.plaid.com",
        "development": "https://development.plaid.com",
        "production": "https://production.plaid.com",
    }
    return env_map.get(env, "https://sandbox.plaid.com")


def get_plaid_client() -> plaid_api.PlaidApi:
    """
    Create and return a configured Plaid API client.

    Requires environment variables:
        - PLAID_CLIENT_ID
        - PLAID_SECRET
        - PLAID_ENV (optional, defaults to 'sandbox')

    Returns:
        Configured PlaidApi instance.

    Raises:
        ValueError: If required environment variables are not set.
    """
    client_id = os.environ.get("PLAID_CLIENT_ID")
    secret = os.environ.get("PLAID_SECRET")

    if not client_id or not secret:
        raise ValueError("PLAID_CLIENT_ID and PLAID_SECRET environment variables must be set")

    configuration = plaid.Configuration(
        host=_get_plaid_host(),
        api_key={
            "clientId": client_id,
            "secret": secret,
        }
    )

    api_client = plaid.ApiClient(configuration)
    return plaid_api.PlaidApi(api_client)


def create_link_token(user_id: int) -> Dict[str, Any]:
    """
    Create a Link token for the Plaid Link flow.

    Args:
        user_id: The user's ID to associate with this Link session.

    Returns:
        Dictionary containing:
            - link_token: Token to use with Plaid Link SDK
            - expiration: Token expiration timestamp
            - request_id: Plaid request ID for debugging

    Raises:
        plaid.ApiException: If Plaid API call fails.
    """
    client = get_plaid_client()

    webhook_url = os.environ.get("PLAID_WEBHOOK_URL")

    kwargs = dict(
        user=LinkTokenCreateRequestUser(
            client_user_id=str(user_id)
        ),
        client_name="BudgetBuddy",
        products=[Products("transactions")],
        country_codes=[CountryCode("US")],
        language="en",
    )
    if webhook_url:
        kwargs["webhook"] = webhook_url

    request = LinkTokenCreateRequest(**kwargs)

    response = client.link_token_create(request)

    return {
        "link_token": response.link_token,
        "expiration": response.expiration,
        "request_id": response.request_id,
    }


def exchange_public_token(public_token: str) -> Tuple[bytes, str]:
    """
    Exchange a public token for an access token.

    Args:
        public_token: The public token received from Plaid Link.

    Returns:
        Tuple of (encrypted_access_token, item_id)
        The access token is encrypted for secure storage.

    Raises:
        plaid.ApiException: If Plaid API call fails.
    """
    client = get_plaid_client()

    request = ItemPublicTokenExchangeRequest(
        public_token=public_token
    )

    response = client.item_public_token_exchange(request)

    # Encrypt the access token before returning
    encrypted_token = encrypt_token(response.access_token)

    return encrypted_token, response.item_id


def get_accounts(encrypted_access_token: bytes) -> Dict[str, Any]:
    """
    Fetch account information for a linked item.

    Args:
        encrypted_access_token: The encrypted access token from database.

    Returns:
        Dictionary containing:
            - accounts: List of account details
            - item: Item metadata including institution info

    Raises:
        plaid.ApiException: If Plaid API call fails.
        ValueError: If token decryption fails.
    """
    client = get_plaid_client()
    access_token = decrypt_token(encrypted_access_token)

    request = AccountsGetRequest(
        access_token=access_token
    )

    response = client.accounts_get(request)

    accounts = []
    for account in response.accounts:
        accounts.append({
            "account_id": account.account_id,
            "name": account.name,
            "official_name": account.official_name,
            "type": _get_enum_value(account.type),
            "subtype": _get_enum_value(account.subtype),
            "mask": account.mask,
            "balances": {
                "available": account.balances.available,
                "current": account.balances.current,
                "limit": account.balances.limit,
            }
        })

    item_info = {
        "item_id": response.item.item_id,
        "institution_id": response.item.institution_id,
    }

    return {
        "accounts": accounts,
        "item": item_info,
        "request_id": response.request_id,
    }


def sync_transactions(
    encrypted_access_token: bytes,
    cursor: Optional[str] = None
) -> Dict[str, Any]:
    """
    Incrementally sync transactions using Plaid's sync API.

    This is the preferred method for getting transactions as it's more
    efficient and provides real-time updates.

    Args:
        encrypted_access_token: The encrypted access token from database.
        cursor: Optional cursor from previous sync for incremental updates.

    Returns:
        Dictionary containing:
            - added: List of new transactions
            - modified: List of modified transactions
            - removed: List of removed transaction IDs
            - next_cursor: Cursor for next sync
            - has_more: Whether more pages are available

    Raises:
        plaid.ApiException: If Plaid API call fails.
    """
    client = get_plaid_client()
    access_token = decrypt_token(encrypted_access_token)

    request = TransactionsSyncRequest(
        access_token=access_token,
        cursor=cursor or "",
    )

    response = client.transactions_sync(request)

    def format_transaction(txn) -> Dict[str, Any]:
        return {
            "transaction_id": txn.transaction_id,
            "account_id": txn.account_id,
            "amount": txn.amount,
            "date": txn.date.isoformat() if txn.date else None,
            "authorized_date": txn.authorized_date.isoformat() if txn.authorized_date else None,
            "name": txn.name,
            "merchant_name": txn.merchant_name,
            "category": txn.personal_finance_category.primary if txn.personal_finance_category else None,
            "category_detailed": txn.personal_finance_category.detailed if txn.personal_finance_category else None,
            "category_confidence": txn.personal_finance_category.confidence_level if txn.personal_finance_category else None,
            "pending": txn.pending,
            "payment_channel": _get_enum_value(txn.payment_channel),
        }

    return {
        "added": [format_transaction(t) for t in response.added],
        "modified": [format_transaction(t) for t in response.modified],
        "removed": [{"transaction_id": t.transaction_id} for t in response.removed],
        "next_cursor": response.next_cursor,
        "has_more": response.has_more,
        "request_id": response.request_id,
    }


def fetch_historical_transactions(
    encrypted_access_token: bytes,
    months: int = 6
) -> List[Dict[str, Any]]:
    """
    Fetch historical transactions for initial data load.

    Uses the transactions/get endpoint for bulk historical data.
    For ongoing updates, use sync_transactions instead.

    Args:
        encrypted_access_token: The encrypted access token from database.
        months: Number of months of history to fetch (default 6).

    Returns:
        List of transaction dictionaries.

    Raises:
        plaid.ApiException: If Plaid API call fails.
    """
    client = get_plaid_client()
    access_token = decrypt_token(encrypted_access_token)

    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=months * 30)

    all_transactions = []
    offset = 0
    total_transactions = None

    while total_transactions is None or offset < total_transactions:
        request = TransactionsGetRequest(
            access_token=access_token,
            start_date=start_date,
            end_date=end_date,
            options=TransactionsGetRequestOptions(
                count=500,
                offset=offset,
            )
        )

        response = client.transactions_get(request)
        total_transactions = response.total_transactions

        for txn in response.transactions:
            all_transactions.append({
                "transaction_id": txn.transaction_id,
                "account_id": txn.account_id,
                "amount": txn.amount,
                "date": txn.date.isoformat() if txn.date else None,
                "authorized_date": txn.authorized_date.isoformat() if txn.authorized_date else None,
                "name": txn.name,
                "merchant_name": txn.merchant_name,
                "category": txn.personal_finance_category.primary if txn.personal_finance_category else None,
                "category_detailed": txn.personal_finance_category.detailed if txn.personal_finance_category else None,
                "category_confidence": txn.personal_finance_category.confidence_level if txn.personal_finance_category else None,
                "pending": txn.pending,
                "payment_channel": _get_enum_value(txn.payment_channel),
            })

        offset += len(response.transactions)

    return all_transactions


def remove_item(encrypted_access_token: bytes) -> bool:
    """
    Remove a linked item (bank connection) from Plaid.

    Args:
        encrypted_access_token: The encrypted access token from database.

    Returns:
        True if removal was successful.

    Raises:
        plaid.ApiException: If Plaid API call fails.
    """
    client = get_plaid_client()
    access_token = decrypt_token(encrypted_access_token)

    request = ItemRemoveRequest(
        access_token=access_token
    )

    client.item_remove(request)
    return True


def get_institution_name(institution_id: str) -> Optional[str]:
    """
    Get the name of an institution by ID.

    Note: This requires the institution_id from the item response.
    For sandbox, this may return placeholder names.

    Args:
        institution_id: Plaid institution ID.

    Returns:
        Institution name or None if not found.
    """
    # In sandbox mode, we'll use a simple mapping for common test institutions
    sandbox_institutions = {
        "ins_109508": "First Platypus Bank",
        "ins_109509": "First Gingham Credit Union",
        "ins_109510": "Tattersall Federal Credit Union",
        "ins_109511": "Tartan Bank",
        "ins_109512": "Houndstooth Bank",
    }

    return sandbox_institutions.get(institution_id, f"Bank ({institution_id})")
