"""
Auth Blueprint — SMS OTP login and user deletion.
"""

import os
from flask import Blueprint, jsonify, request
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
from dotenv import load_dotenv

from db_models import (
    get_user_by_phone,
    create_user,
    get_profile,
    get_user,
    delete_user_cascade,
)

load_dotenv()

auth_bp = Blueprint('auth', __name__)

# Credentials
client = Client(os.getenv('TWILIO_ACCOUNT_SID'), os.getenv('TWILIO_AUTH_TOKEN'))
VERIFY_SERVICE_ID = os.getenv('TWILIO_VERIFY_SERVICE_ID')

# Add this variable to your .env: FLASK_ENV=development
FLASK_ENV = os.getenv('FLASK_ENV', 'production')

@auth_bp.route("/v1/send_sms_code", methods=["POST"])
def send_sms_code():
    data = request.get_json()
    phone_number = data.get("phone_number", "").strip()

    # --- DEV BYPASS ---
    if FLASK_ENV == 'development' and phone_number == "+15005550006":
        return jsonify({"status": "pending", "message": "DEV MODE: Use code 123456"})
    # ------------------

    try:
        verification = client.verify \
            .v2 \
            .services(VERIFY_SERVICE_ID) \
            .verifications \
            .create(to=phone_number, channel='sms')
        return jsonify({"status": verification.status})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@auth_bp.route("/v1/verify_code", methods=["POST"])
def verify_code():
    data = request.get_json()
    phone_number = data.get("phone_number", "").strip()
    code = data.get("code", "").strip()

    # --- DEV BYPASS ---
    if FLASK_ENV == 'development' and phone_number == "+15005550006" and code == "123456":
        approved = True
    else:
        try:
            check = client.verify.v2.services(VERIFY_SERVICE_ID) \
                .verification_checks.create(to=phone_number, code=code)
            approved = (check.status == "approved")
        except Exception:
            approved = False
    # ------------------

    if approved:
        user = get_user_by_phone(phone_number) or create_user(phone_number)
        profile = get_profile(user.key.id)
        return jsonify({
            "token": user.key.id,
            "hasProfile": profile is not None,
            "name": user.get('name'),
        })
    
    return jsonify({"error": "Invalid code"}), 401

@auth_bp.route("/v1/user", methods=["DELETE"])
def delete_user():
    user_id = request.args.get("userId")
    if not user_id:
        return jsonify({"error": "userId is required"}), 400

    try:
        user_id = int(user_id)
        user = get_user(user_id)
        if user:
            delete_user_cascade(user_id)
        return "", 204
    except ValueError:
        return jsonify({"error": "Invalid userId"}), 400
