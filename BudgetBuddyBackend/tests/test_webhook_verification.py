"""
Tests for the Plaid webhook signature verification middleware.

Tests verify:
1. Requests without Plaid-Verification header are rejected (401)
2. Requests with invalid JWT are rejected (401)
3. Requests with valid JWT but wrong body hash are rejected (401)
4. Valid requests pass through
"""

import os
import sys
import hashlib
import json
import time
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from flask import Flask, jsonify
from middleware.webhook import verify_plaid_webhook


@pytest.fixture
def app():
    """Create a minimal Flask app with a test route protected by @verify_plaid_webhook."""
    app = Flask(__name__)
    app.config['TESTING'] = True

    @app.route("/webhook", methods=["POST"])
    @verify_plaid_webhook
    def webhook_route():
        return jsonify({"received": True})

    return app


@pytest.fixture
def client(app):
    return app.test_client()


class TestMissingHeader:
    def test_no_verification_header_returns_401(self, client):
        resp = client.post(
            "/webhook",
            json={"webhook_type": "TRANSACTIONS"},
        )
        assert resp.status_code == 401
        assert "Missing" in resp.get_json()["error"]


class TestInvalidToken:
    def test_garbage_token_returns_401(self, client):
        resp = client.post(
            "/webhook",
            json={"webhook_type": "TRANSACTIONS"},
            headers={"Plaid-Verification": "not.a.jwt"},
        )
        assert resp.status_code == 401


class TestValidVerification:
    @patch("middleware.webhook._get_public_key")
    def test_valid_signature_passes(self, mock_get_key, client):
        """Simulate a valid webhook by mocking JWT decode to pass."""
        body = json.dumps({"webhook_type": "TRANSACTIONS", "webhook_code": "DEFAULT_UPDATE"})
        body_hash = hashlib.sha256(body.encode()).hexdigest()

        claims = {
            "iat": int(time.time()),
            "request_body_sha256": body_hash,
        }

        # Mock the full JWT verification flow
        with patch("middleware.webhook.jwt.get_unverified_header", return_value={"kid": "test-kid", "alg": "ES256"}), \
             patch("middleware.webhook.jwt.decode", return_value=claims):

            mock_get_key.return_value = "mock-key"

            resp = client.post(
                "/webhook",
                data=body,
                content_type="application/json",
                headers={"Plaid-Verification": "valid.mock.token"},
            )
            assert resp.status_code == 200
            assert resp.get_json()["received"] is True

    @patch("middleware.webhook._get_public_key")
    def test_body_hash_mismatch_returns_401(self, mock_get_key, client):
        """If the body hash doesn't match, reject."""
        claims = {
            "iat": int(time.time()),
            "request_body_sha256": "wrong_hash",
        }

        with patch("middleware.webhook.jwt.get_unverified_header", return_value={"kid": "test-kid", "alg": "ES256"}), \
             patch("middleware.webhook.jwt.decode", return_value=claims):

            mock_get_key.return_value = "mock-key"

            resp = client.post(
                "/webhook",
                json={"webhook_type": "TRANSACTIONS"},
                headers={"Plaid-Verification": "valid.mock.token"},
            )
            assert resp.status_code == 401
            assert "hash mismatch" in resp.get_json()["error"]

    @patch("middleware.webhook._get_public_key")
    def test_expired_iat_returns_401(self, mock_get_key, client):
        """If the iat is too old (>5 min), reject."""
        body = json.dumps({"webhook_type": "TRANSACTIONS"})
        body_hash = hashlib.sha256(body.encode()).hexdigest()

        claims = {
            "iat": int(time.time()) - 600,  # 10 minutes ago
            "request_body_sha256": body_hash,
        }

        with patch("middleware.webhook.jwt.get_unverified_header", return_value={"kid": "test-kid", "alg": "ES256"}), \
             patch("middleware.webhook.jwt.decode", return_value=claims):

            mock_get_key.return_value = "mock-key"

            resp = client.post(
                "/webhook",
                data=body,
                content_type="application/json",
                headers={"Plaid-Verification": "valid.mock.token"},
            )
            assert resp.status_code == 401
            assert "expired" in resp.get_json()["error"]
