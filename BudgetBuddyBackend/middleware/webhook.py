"""
Plaid webhook signature verification.

Verifies the Plaid-Verification JWT header on incoming webhooks to ensure
requests genuinely originate from Plaid. Uses Plaid's JWK-based verification:
1. Extract JWT from Plaid-Verification header
2. Decode header to get the key ID (kid)
3. Fetch the corresponding public key from Plaid
4. Verify JWT signature (ES256) and claims
5. Compare SHA-256 hash of request body with the claim in the token
"""

import hashlib
import json
import time
from functools import wraps

import jwt
from jwt.algorithms import ECAlgorithm
from flask import request, jsonify

from services.plaid_service import get_plaid_client
from plaid.model.webhook_verification_key_get_request import WebhookVerificationKeyGetRequest

# Cache fetched JWKs to avoid repeated API calls (kid -> JWK dict)
_key_cache: dict = {}


def _get_public_key(kid: str) -> str:
    """Fetch and cache the Plaid webhook verification public key for a given kid."""
    if kid in _key_cache:
        return _key_cache[kid]

    client = get_plaid_client()
    req = WebhookVerificationKeyGetRequest(key_id=kid)
    response = client.webhook_verification_key_get(req)
    jwk = response.key.to_dict()

    # Convert JWK to PEM for PyJWT
    pem_key = ECAlgorithm.from_jwk(json.dumps(jwk))
    _key_cache[kid] = pem_key
    return pem_key


def verify_plaid_webhook(f):
    """Decorator that verifies the Plaid-Verification JWT on webhook requests."""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get("Plaid-Verification")
        if not token:
            return jsonify({"error": "Missing Plaid-Verification header"}), 401

        try:
            # Decode header without verification to get the kid
            unverified_header = jwt.get_unverified_header(token)
            kid = unverified_header.get("kid")
            if not kid:
                return jsonify({"error": "No kid in JWT header"}), 401

            # Fetch the public key
            public_key = _get_public_key(kid)

            # Verify the JWT
            claims = jwt.decode(
                token,
                public_key,
                algorithms=["ES256"],
                options={
                    "require": ["iat", "request_body_sha256"],
                },
            )

            # Check that the token isn't too old (5 minute window)
            issued_at = claims.get("iat", 0)
            if abs(time.time() - issued_at) > 300:
                return jsonify({"error": "Webhook token expired"}), 401

            # Verify request body hash
            body = request.get_data()
            body_hash = hashlib.sha256(body).hexdigest()
            if body_hash != claims.get("request_body_sha256"):
                return jsonify({"error": "Request body hash mismatch"}), 401

        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Webhook token expired"}), 401
        except jwt.InvalidTokenError as e:
            return jsonify({"error": f"Invalid webhook token: {e}"}), 401
        except Exception as e:
            print(f"[WEBHOOK] Verification error: {e}")
            return jsonify({"error": "Webhook verification failed"}), 401

        return f(*args, **kwargs)

    return decorated
