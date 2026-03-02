"""
Auth Blueprint — SMS OTP login and user deletion.
"""

import random
import string
from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request

from db_models import (
    create_otp,
    get_pending_otp,
    mark_otp_verified,
    delete_otps_for_phone,
    get_user_by_phone,
    create_user,
    get_profile,
    get_user,
    delete_user_cascade,
)

auth_bp = Blueprint('auth', __name__)

# Demo account for App Store review — always accepts a fixed OTP, no SMS sent.
DEMO_PHONE = "+15550001234"
DEMO_OTP   = "123456"


def send_via_twilio(phone_number: str, code: str):
    """Placeholder for Twilio SMS. Prints to console in development."""
    print(f"\n{'='*50}")
    print(f"SMS to {phone_number}: Your BudgetBuddy code is {code}")
    print(f"{'='*50}\n")


@auth_bp.route("/v1/send_sms_code", methods=["POST"])
def send_sms_code():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    phone_number = data.get("phone_number", "").strip()
    if not phone_number:
        return jsonify({"error": "Phone number is required"}), 400

    if not phone_number.startswith("+") or not (10 <= len(phone_number) <= 16):
        return jsonify({"error": "Invalid phone number format. Use E.164 format (e.g., +14155551234)"}), 400

    is_demo = (phone_number == DEMO_PHONE)
    code = DEMO_OTP if is_demo else ''.join(random.choices(string.digits, k=6))
    expires_at = datetime.utcnow() + timedelta(minutes=5)

    # Invalidate existing unused codes
    delete_otps_for_phone(phone_number)

    create_otp(phone_number, code, expires_at)
    if not is_demo:
        send_via_twilio(phone_number, code)

    return jsonify({"status": "success"})


@auth_bp.route("/v1/verify_code", methods=["POST"])
def verify_code():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    phone_number = data.get("phone_number", "").strip()
    code = data.get("code", "").strip()

    if not phone_number or not code:
        return jsonify({"error": "Phone number and code are required"}), 400

    otp = get_pending_otp(phone_number)
    if not otp:
        return jsonify({"error": "No verification code found. Please request a new one."}), 400

    expires_at = otp['expires_at']
    if hasattr(expires_at, 'tzinfo') and expires_at.tzinfo is not None:
        expires_at = expires_at.replace(tzinfo=None)
    if datetime.utcnow() > expires_at:
        return jsonify({"error": "Verification code has expired. Please request a new one."}), 400

    if otp['code'] != code:
        return jsonify({"error": "Invalid verification code"}), 401

    mark_otp_verified(otp.key)

    user = get_user_by_phone(phone_number)
    if not user:
        user = create_user(phone_number)

    user_id = user.key.id
    profile = get_profile(user_id)

    return jsonify({
        "token": user_id,
        "hasProfile": profile is not None,
        "name": user.get('name'),
    })


@auth_bp.route("/v1/user", methods=["DELETE"])
def delete_user():
    user_id = request.args.get("userId")
    if not user_id:
        return jsonify({"error": "userId is required"}), 400

    try:
        user_id = int(user_id)
    except ValueError:
        return jsonify({"error": "Invalid userId"}), 400

    user = get_user(user_id)
    if user:
        delete_user_cascade(user_id)

    return "", 204
