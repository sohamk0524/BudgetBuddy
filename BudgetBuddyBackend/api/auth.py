"""
Auth Blueprint — Firebase phone auth verification and user management.

The iOS app handles the full SMS OTP flow via the Firebase SDK.
After the user verifies their phone number client-side, it sends the
Firebase ID token here. We verify it, then create/return our app user.
"""

import os
from firebase_admin import auth as firebase_auth
from flask import Blueprint, jsonify, request
from dotenv import load_dotenv

from middleware.auth import require_auth
from db_models import (
    get_user_by_firebase_uid,
    create_user,
    get_profile,
    get_user,
    delete_user_cascade,
)

load_dotenv()

auth_bp = Blueprint('auth', __name__)

@auth_bp.route("/v1/auth/firebase", methods=["POST"])
def firebase_login():
    """
    Called after Firebase phone auth completes on iOS.
    Body: { "idToken": "<firebase_id_token>" }
    Returns: { "token": "<firebase_uid>", "hasProfile": bool, "name": str|null }
    """
    data = request.get_json()
    id_token = (data or {}).get("idToken", "").strip()

    if not id_token:
        return jsonify({"error": "idToken is required"}), 400

    try:
        decoded = firebase_auth.verify_id_token(id_token)
    except firebase_auth.ExpiredIdTokenError:
        return jsonify({"error": "Token expired"}), 401
    except firebase_auth.InvalidIdTokenError:
        return jsonify({"error": "Invalid token"}), 401
    except Exception as e:
        return jsonify({"error": str(e)}), 401

    firebase_uid = decoded["uid"]
    phone_number = decoded.get("phone_number")

    # Create user record if this is their first login
    user = get_user_by_firebase_uid(firebase_uid) or create_user(firebase_uid, phone=phone_number)
    profile = get_profile(firebase_uid)

    return jsonify({
        "token": firebase_uid,
        "hasProfile": profile is not None,
        "name": user.get("name"),
    })


@auth_bp.route("/v1/user", methods=["DELETE"])
@require_auth
def delete_user():
    user_id = request.args.get("userId")
    if not user_id:
        return jsonify({"error": "userId is required"}), 400

    user = get_user(user_id)
    if user:
        delete_user_cascade(user_id)
    return "", 204
