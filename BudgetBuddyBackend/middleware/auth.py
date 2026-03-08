"""
Authentication & authorization middleware for BudgetBuddy API.

Provides a @require_auth decorator that:
1. Extracts Bearer token from the Authorization header
2. Verifies it as a valid Firebase ID token
3. Sets g.user_id to the authenticated user's Firebase UID
4. Optionally verifies the authenticated user matches the requested userId
"""

from functools import wraps
from flask import request, jsonify, g
from firebase_admin import auth as firebase_auth


def _extract_requested_user_id(kwargs):
    """Extract the userId the request is trying to access from various sources."""
    # 1. Path parameter (e.g., /user/profile/<user_id>)
    user_id = kwargs.get("user_id")
    if user_id:
        return user_id

    # 2. Query parameter (e.g., ?userId=...)
    user_id = request.args.get("userId")
    if user_id:
        return user_id

    # 3. JSON body field
    if request.is_json:
        data = request.get_json(silent=True)
        if data:
            user_id = data.get("userId") or data.get("user_id")
            if user_id:
                return user_id

    # 4. Form data field (multipart uploads)
    user_id = request.form.get("userId")
    if user_id:
        return user_id

    return None


def require_auth(f):
    """Decorator that enforces Firebase token authentication and user ownership.

    Usage:
        @some_bp.route("/some/path/<user_id>")
        @require_auth
        def some_endpoint(user_id):
            # g.user_id is set to the authenticated Firebase UID
            ...
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        # CORS preflight requests don't carry auth headers
        if request.method == "OPTIONS":
            return f(*args, **kwargs)

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "Authorization required"}), 401

        token = auth_header[7:]
        try:
            decoded = firebase_auth.verify_id_token(token)
            g.user_id = decoded["uid"]
        except firebase_auth.ExpiredIdTokenError:
            return jsonify({"error": "Token expired"}), 401
        except firebase_auth.InvalidIdTokenError:
            return jsonify({"error": "Invalid token"}), 401
        except Exception:
            return jsonify({"error": "Authentication failed"}), 401

        # Verify the authenticated user matches the requested user
        requested_user_id = _extract_requested_user_id(kwargs)
        if requested_user_id and requested_user_id != g.user_id:
            return jsonify({"error": "Forbidden"}), 403

        return f(*args, **kwargs)

    return decorated
