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

# Demo account for App Store review
DEMO_PHONE = "+15550001234"
DEMO_OTP   = "123456"

@auth_bp.route("/v1/send_sms_code", methods=["POST"])
def send_sms_code():
    data = request.get_json()
    if not data or "phone_number" not in data:
        return jsonify({"error": "Phone number is required"}), 400
    
    phone_number = data.get("phone_number", "").strip()

    # 1. Validation for phone format
    if not phone_number.startswith("+") or not (10 <= len(phone_number) <= 16):
        return jsonify({"error": "Invalid format. Use E.164 (e.g., +14155551234)"}), 400

    # 2. Handle Demo Account
    if phone_number == DEMO_PHONE:
        return jsonify({"status": "pending", "message": "Demo mode active"})

    # 3. Handle Real Twilio Verify
    try:
        verification = client.verify \
            .v2 \
            .services(VERIFY_SERVICE_ID) \
            .verifications \
            .create(to=phone_number, channel='sms')
        
        return jsonify({"status": verification.status})
    except TwilioRestException as e:
        return jsonify({"error": f"Twilio error: {e.msg}"}), e.status
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@auth_bp.route("/v1/verify_code", methods=["POST"])
def verify_code():
    data = request.get_json()
    phone_number = data.get("phone_number", "").strip()
    code = data.get("code", "").strip()

    if not phone_number or not code:
        return jsonify({"error": "Phone and code required"}), 400

    # 1. Check for Demo Account bypass
    is_approved = False
    if phone_number == DEMO_PHONE and code == DEMO_OTP:
        is_approved = True
    else:
        # 2. Check with Twilio Verify
        try:
            verification_check = client.verify \
                .v2 \
                .services(VERIFY_SERVICE_ID) \
                .verification_checks \
                .create(to=phone_number, code=code)
            is_approved = (verification_check.status == "approved")
        except Exception as e:
            return jsonify({"error": f"Verification failed: {str(e)}"}), 400

    # 3. Process Login/Registration
    if is_approved:
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
    
    return jsonify({"error": "Invalid or expired code"}), 401

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
