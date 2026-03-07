"""
Receipt Blueprint — scan receipts via Claude Vision, attach to transactions.
"""

import json
from datetime import datetime

from flask import Blueprint, jsonify, request

from db_models import (
    get_user,
    find_matching_transaction,
    update_transaction_receipt,
    create_manual_transaction,
)
from services.receipt_service import analyze_receipt

receipt_bp = Blueprint('receipt', __name__)

_SUPPORTED_MEDIA_TYPES = {
    'image/jpeg': 'image/jpeg',
    'image/png': 'image/png',
    'image/heic': 'image/jpeg',   # Claude doesn't support HEIC; convert at client or treat as jpeg
    'image/jpg': 'image/jpeg',
}


def _detect_media_type(file) -> str:
    """Detect MIME type from filename or content-type header."""
    content_type = file.content_type or ''
    if content_type in _SUPPORTED_MEDIA_TYPES:
        return _SUPPORTED_MEDIA_TYPES[content_type]
    filename = (file.filename or '').lower()
    if filename.endswith('.png'):
        return 'image/png'
    return 'image/jpeg'


@receipt_bp.route("/receipt/analyze", methods=["POST"])
def analyze_receipt_endpoint():
    """
    Accept a receipt image upload and return Claude Vision analysis.

    Form data:
    - file: image file (JPEG/PNG/HEIC)
    - userId: int
    """
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files['file']
    user_id = request.form.get('userId')

    if not user_id:
        return jsonify({"error": "userId is required"}), 400

    user = get_user(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    image_data = file.read()
    if not image_data:
        return jsonify({"error": "Empty file"}), 400

    media_type = _detect_media_type(file)

    try:
        result = analyze_receipt(image_data, media_type)
    except Exception as e:
        print(f"Receipt analysis error: {e}")
        return jsonify({"error": f"Failed to analyze receipt: {str(e)}"}), 500

    return jsonify(result)


@receipt_bp.route("/receipt/attach", methods=["POST"])
def attach_receipt():
    """
    Attach an analyzed receipt to an existing Plaid transaction (enrich) or
    create a new ManualTransaction with receipt data.

    JSON body:
    {
      "userId": int,
      "merchant": str,
      "total": float,
      "items": [...],
      "essentialTotal": float,
      "discretionaryTotal": float,
      "date": "YYYY-MM-DD",
      "imageUrl": str (optional)
    }
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    user_id = data.get('userId')
    merchant = data.get('merchant', '')
    total = data.get('total', 0.0)
    items = data.get('items', [])
    category = data.get('category', 'other')
    date_str = data.get('date') or datetime.utcnow().strftime('%Y-%m-%d')
    image_url = data.get('imageUrl')

    if not user_id:
        return jsonify({"error": "userId is required"}), 400

    user = get_user(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    receipt_items_json = json.dumps(items)

    # Use the category directly as sub_category
    valid_categories = ('food', 'drink', 'groceries', 'transportation', 'entertainment', 'other')
    sub_category = category.lower() if category.lower() in valid_categories else 'other'

    # Try to find a matching Plaid transaction to enrich
    matching_txn = find_matching_transaction(user_id, total, date_str, merchant)

    if matching_txn:
        updated = update_transaction_receipt(
            txn_id=matching_txn.key.id,
            receipt_items_json=receipt_items_json,
            essential_amount=None,
            discretionary_amount=None,
            sub_category=sub_category,
            image_url=image_url,
        )
        return jsonify({
            "transactionId": matching_txn.key.id,
            "source": "plaid",
            "enriched": True,
        })

    # No match — create a new ManualTransaction
    manual_txn = create_manual_transaction(
        user_id,
        amount=round(total, 2),
        date=date_str,
        store=merchant,
        notes=f"Receipt: {merchant}",
        sub_category=sub_category,
        essential_amount=None,
        discretionary_amount=None,
        receipt_items=receipt_items_json,
        receipt_image_url=image_url,
        pending_plaid_reconcile=True,
        source='receipt',
    )

    return jsonify({
        "transactionId": manual_txn.key.id,
        "source": "manual",
        "enriched": False,
    }), 201
