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

# --- App Store Review Credentials ---
# These MUST work in production so reviewers can enter your app.
DEMO_PHONE = "+15550001234"
DEMO_OTP   = "123456"

# --- Dev/Local Credentials ---
# Used for your local testing with FLASK_ENV=development
MAGIC_PHONE = "+15005550006"
MAGIC_OTP   = "123456"

# Credentials
client = Client(os.getenv('TWILIO_ACCOUNT_SID'), os.getenv('TWILIO_AUTH_TOKEN'))
VERIFY_SERVICE_ID = os.getenv('TWILIO_VERIFY_SERVICE_ID')
FLASK_ENV = os.getenv('FLASK_ENV', 'production')

@auth_bp.route("/v1/send_sms_code", methods=["POST"])
def send_sms_code():
    data = request.get_json()
    phone_number = data.get("phone_number", "").strip()

    # 1. Check for Demo Account (Always allow in Prod and Dev)
    if phone_number == DEMO_PHONE:
        return jsonify({"status": "pending", "message": "Demo mode: use 123456"})

    # 2. Check for Dev "Magic" Number
    if FLASK_ENV == 'development' and phone_number == MAGIC_PHONE:
        return jsonify({"status": "pending", "message": "DEV MODE: Use code 123456"})

    # 3. Real Twilio Verify Request
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

    approved = False

    # 1. Validate Demo Account
    if phone_number == DEMO_PHONE and code == DEMO_OTP:
        approved = True

    # 2. Validate Dev Magic Number
    elif FLASK_ENV == 'development' and phone_number == MAGIC_PHONE and code == MAGIC_OTP:
        approved = True

    # 3. Validate via Twilio Verify
    else:
        try:
            check = client.verify.v2.services(VERIFY_SERVICE_ID) \
                .verification_checks.create(to=phone_number, code=code)
            approved = (check.status == "approved")
        except Exception:
            approved = False

    if approved:
        # Create user if they don't exist
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
