"""
Push notification service for BudgetBuddy.
Sends APNs push notifications for transaction alerts and classification prompts.
Uses PyAPNs2 for Apple Push Notification service.
"""

import os
import json
from typing import Optional, Dict, Any


def send_push_notification(
    user_id: int,
    title: str,
    body: str,
    data: Optional[Dict[str, Any]] = None
) -> int:
    """
    Send a push notification to all of a user's registered devices.
    Returns the number of notifications sent.
    """
    from db_models import get_active_device_tokens, get_client

    tokens = get_active_device_tokens(user_id)
    if not tokens:
        return 0

    client = get_client()
    sent = 0
    for device in tokens:
        try:
            _send_apns(device['token'], title, body, data)
            sent += 1
        except Exception as e:
            print(f"Failed to send push to device {device['token'][:20]}...: {e}")
            if "BadDeviceToken" in str(e) or "Unregistered" in str(e):
                device['is_active'] = False
                client.put(device)

    return sent


def _send_apns(
    device_token: str,
    title: str,
    body: str,
    data: Optional[Dict[str, Any]] = None
) -> None:
    """
    Send a single APNs notification.
    In production, this uses PyAPNs2 with an APNs auth key.
    For development/sandbox, we log the notification.
    """
    apns_key_path = os.environ.get("APNS_KEY_PATH")
    apns_key_id = os.environ.get("APNS_KEY_ID")
    apns_team_id = os.environ.get("APNS_TEAM_ID")
    apns_bundle_id = os.environ.get("APNS_BUNDLE_ID", "com.budgetbuddy.app")

    if apns_key_path and apns_key_id and apns_team_id:
        try:
            from apns2.client import APNsClient
            from apns2.payload import Payload
            from apns2.credentials import TokenCredentials

            credentials = TokenCredentials(
                auth_key_path=apns_key_path,
                auth_key_id=apns_key_id,
                team_id=apns_team_id
            )

            client = APNsClient(
                credentials=credentials,
                use_sandbox=os.environ.get("APNS_SANDBOX", "true").lower() == "true"
            )

            payload = Payload(
                alert={"title": title, "body": body},
                sound="default",
                custom=data or {}
            )

            client.send_notification(device_token, payload, apns_bundle_id)
        except ImportError:
            print(f"[PUSH] PyAPNs2 not installed. Notification: {title} - {body}")
    else:
        print(f"\n{'='*50}")
        print(f"[PUSH NOTIFICATION] to token: {device_token[:20]}...")
        print(f"  Title: {title}")
        print(f"  Body: {body}")
        if data:
            print(f"  Data: {json.dumps(data)}")
        print(f"{'='*50}\n")


def notify_new_transactions(user_id: int, transactions: list) -> None:
    """
    Send push notification summarizing new transactions.
    Accepts a list of Datastore transaction entities.
    """
    if not transactions:
        return

    total_amount = sum(abs(t.get('amount') or 0) for t in transactions if (t.get('amount') or 0) > 0)
    count = len(transactions)

    if count == 1:
        txn = transactions[0]
        merchant = txn.get('merchant_name') or txn.get('name')
        category = txn.get('sub_category') or "unclassified"
        title = "New Transaction"
        body = f"${abs(txn.get('amount') or 0):.2f} at {merchant}"
        if category != "unclassified":
            body += f" ({category})"
    else:
        title = f"{count} New Transactions"
        body = f"${total_amount:.2f} total spending detected"

        cats = {}
        for t in transactions:
            cat = t.get('sub_category') or "unclassified"
            cats[cat] = cats.get(cat, 0) + 1
        parts = [f"{v} {k}" for k, v in cats.items() if v > 0]
        if parts:
            body += f" — {', '.join(parts)}"

    send_push_notification(
        user_id,
        title=title,
        body=body,
        data={"type": "new_transactions", "count": count}
    )


def notify_classification_needed(user_id: int, merchant_name: str, amount: float) -> None:
    """Send a push notification prompting the user to classify a merchant."""
    send_push_notification(
        user_id,
        title="Classify This Expense",
        body=f"How would you classify ${amount:.2f} at {merchant_name}? Essential, discretionary, or mixed?",
        data={"type": "classify_prompt", "merchantName": merchant_name}
    )
