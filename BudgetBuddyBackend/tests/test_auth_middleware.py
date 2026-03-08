"""
Tests for the authentication middleware.

Tests verify:
1. Requests without Authorization header are rejected (401)
2. Requests with invalid tokens are rejected (401)
3. Requests where authenticated user != requested user are rejected (403)
4. Valid requests pass through
5. OPTIONS (CORS preflight) passes without auth
"""

import os
import sys
import pytest
from unittest.mock import patch, MagicMock

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from flask import Flask, jsonify, g
from middleware.auth import require_auth


@pytest.fixture
def app():
    """Create a minimal Flask app with test routes protected by @require_auth."""
    app = Flask(__name__)
    app.config['TESTING'] = True

    @app.route("/test/path/<user_id>", methods=["GET"])
    @require_auth
    def path_param_route(user_id):
        return jsonify({"user_id": user_id, "auth_user": g.user_id})

    @app.route("/test/query", methods=["GET"])
    @require_auth
    def query_param_route():
        return jsonify({"auth_user": g.user_id})

    @app.route("/test/body", methods=["POST"])
    @require_auth
    def body_route():
        return jsonify({"auth_user": g.user_id})

    @app.route("/test/options", methods=["POST", "OPTIONS"])
    @require_auth
    def options_route():
        return jsonify({"ok": True})

    return app


@pytest.fixture
def client(app):
    return app.test_client()


def _mock_verify(uid):
    """Helper: patch firebase_auth.verify_id_token to return a given uid."""
    return patch(
        "middleware.auth.firebase_auth.verify_id_token",
        return_value={"uid": uid},
    )


class TestNoAuthHeader:
    """Requests without Authorization header should be rejected."""

    def test_missing_header_returns_401(self, client):
        resp = client.get("/test/path/user123")
        assert resp.status_code == 401
        assert "Authorization required" in resp.get_json()["error"]

    def test_wrong_scheme_returns_401(self, client):
        resp = client.get(
            "/test/path/user123",
            headers={"Authorization": "Basic abc123"},
        )
        assert resp.status_code == 401


class TestInvalidToken:
    """Requests with invalid/expired tokens should be rejected."""

    def test_expired_token_returns_401(self, client):
        from firebase_admin import auth as firebase_auth

        with patch(
            "middleware.auth.firebase_auth.verify_id_token",
            side_effect=firebase_auth.ExpiredIdTokenError("expired", cause=None),
        ):
            resp = client.get(
                "/test/path/user123",
                headers={"Authorization": "Bearer expired_token"},
            )
            assert resp.status_code == 401
            assert "expired" in resp.get_json()["error"].lower()

    def test_invalid_token_returns_401(self, client):
        from firebase_admin import auth as firebase_auth

        with patch(
            "middleware.auth.firebase_auth.verify_id_token",
            side_effect=firebase_auth.InvalidIdTokenError("invalid"),
        ):
            resp = client.get(
                "/test/path/user123",
                headers={"Authorization": "Bearer bad_token"},
            )
            assert resp.status_code == 401
            assert "Invalid" in resp.get_json()["error"]


class TestUserOwnership:
    """Authenticated user must match the requested user."""

    def test_matching_path_param_succeeds(self, client):
        with _mock_verify("user123"):
            resp = client.get(
                "/test/path/user123",
                headers={"Authorization": "Bearer valid_token"},
            )
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["user_id"] == "user123"
            assert data["auth_user"] == "user123"

    def test_mismatched_path_param_returns_403(self, client):
        with _mock_verify("user123"):
            resp = client.get(
                "/test/path/other_user",
                headers={"Authorization": "Bearer valid_token"},
            )
            assert resp.status_code == 403
            assert "Forbidden" in resp.get_json()["error"]

    def test_matching_query_param_succeeds(self, client):
        with _mock_verify("user123"):
            resp = client.get(
                "/test/query?userId=user123",
                headers={"Authorization": "Bearer valid_token"},
            )
            assert resp.status_code == 200

    def test_mismatched_query_param_returns_403(self, client):
        with _mock_verify("user123"):
            resp = client.get(
                "/test/query?userId=other_user",
                headers={"Authorization": "Bearer valid_token"},
            )
            assert resp.status_code == 403

    def test_matching_body_param_succeeds(self, client):
        with _mock_verify("user123"):
            resp = client.post(
                "/test/body",
                json={"userId": "user123"},
                headers={"Authorization": "Bearer valid_token"},
            )
            assert resp.status_code == 200

    def test_mismatched_body_param_returns_403(self, client):
        with _mock_verify("user123"):
            resp = client.post(
                "/test/body",
                json={"userId": "other_user"},
                headers={"Authorization": "Bearer valid_token"},
            )
            assert resp.status_code == 403

    def test_no_user_id_in_request_still_succeeds(self, client):
        """If no userId is found in the request, ownership check is skipped."""
        with _mock_verify("user123"):
            resp = client.post(
                "/test/body",
                json={"message": "hello"},
                headers={"Authorization": "Bearer valid_token"},
            )
            assert resp.status_code == 200


class TestOptionsPassthrough:
    """CORS preflight (OPTIONS) should pass without auth."""

    def test_options_skips_auth(self, client):
        resp = client.options("/test/options")
        assert resp.status_code == 200
