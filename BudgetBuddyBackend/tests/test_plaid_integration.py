"""
Tests for Plaid integration endpoints and services.
Uses mocked Plaid client to avoid real API calls during testing.
"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, date


class TestEncryptionService:
    """Test encryption/decryption of access tokens."""

    def test_encrypt_decrypt_roundtrip(self, app):
        """Test that encrypting then decrypting returns original value."""
        from services.encryption_service import encrypt_token, decrypt_token

        with patch.dict('os.environ', {'FERNET_KEY': 'VGhpcyBpcyBhIDMyIGJ5dGUga2V5IGZvciB0ZXN0cyE='}):
            original = "access-sandbox-test-token-123"
            encrypted = encrypt_token(original)

            assert encrypted != original.encode()
            assert isinstance(encrypted, bytes)

            decrypted = decrypt_token(encrypted)
            assert decrypted == original

    def test_encrypt_empty_token_raises(self, app):
        """Test that encrypting empty string raises ValueError."""
        from services.encryption_service import encrypt_token

        with patch.dict('os.environ', {'FERNET_KEY': 'VGhpcyBpcyBhIDMyIGJ5dGUga2V5IGZvciB0ZXN0cyE='}):
            with pytest.raises(ValueError, match="Cannot encrypt empty token"):
                encrypt_token("")

    def test_decrypt_empty_ciphertext_raises(self, app):
        """Test that decrypting empty bytes raises ValueError."""
        from services.encryption_service import decrypt_token

        with patch.dict('os.environ', {'FERNET_KEY': 'VGhpcyBpcyBhIDMyIGJ5dGUga2V5IGZvciB0ZXN0cyE='}):
            with pytest.raises(ValueError, match="Cannot decrypt empty ciphertext"):
                decrypt_token(b"")

    def test_missing_fernet_key_raises(self, app):
        """Test that missing FERNET_KEY raises ValueError."""
        from services.encryption_service import encrypt_token

        with patch.dict('os.environ', {}, clear=True):
            with pytest.raises(ValueError, match="FERNET_KEY environment variable is not set"):
                encrypt_token("test")


class TestPlaidLinkToken:
    """Test Plaid Link token creation."""

    def test_create_link_token_success(self, client, sample_user_for_plaid):
        """Test successful link token creation."""
        mock_response = MagicMock()
        mock_response.link_token = "link-sandbox-test-token"
        mock_response.expiration = "2026-02-10T00:00:00Z"
        mock_response.request_id = "test-request-id"

        with patch('services.plaid_service.get_plaid_client') as mock_client:
            mock_client.return_value.link_token_create.return_value = mock_response

            response = client.post('/plaid/link-token', json={
                "userId": sample_user_for_plaid
            })

            assert response.status_code == 200
            data = response.get_json()
            assert "linkToken" in data
            assert data["linkToken"] == "link-sandbox-test-token"

    def test_create_link_token_missing_user_id(self, client):
        """Test link token creation without userId."""
        response = client.post('/plaid/link-token',
                               json={"userId": None},
                               content_type='application/json')

        assert response.status_code == 400
        assert "userId is required" in response.get_json()["error"]

    def test_create_link_token_user_not_found(self, client):
        """Test link token creation with non-existent user."""
        response = client.post('/plaid/link-token', json={
            "userId": 99999
        })

        assert response.status_code == 404
        assert "User not found" in response.get_json()["error"]


class TestPlaidTokenExchange:
    """Test Plaid public token exchange."""

    def test_exchange_token_success(self, client, sample_user_for_plaid, mock_plaid_exchange):
        """Test successful token exchange and data fetching."""
        response = client.post('/plaid/exchange-token', json={
            "userId": sample_user_for_plaid,
            "publicToken": "public-sandbox-test-token",
            "institutionId": "ins_109508",
            "institutionName": "First Platypus Bank"
        })

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert "itemId" in data
        assert "accounts" in data
        assert len(data["accounts"]) > 0

    def test_exchange_token_missing_fields(self, client, sample_user_for_plaid):
        """Test token exchange with missing required fields."""
        response = client.post('/plaid/exchange-token', json={
            "userId": sample_user_for_plaid
        })

        assert response.status_code == 400
        assert "publicToken are required" in response.get_json()["error"]


class TestPlaidAccounts:
    """Test Plaid accounts retrieval."""

    def test_get_accounts_empty(self, client, sample_user_for_plaid):
        """Test getting accounts for user with no linked items."""
        response = client.get(f'/plaid/accounts/{sample_user_for_plaid}')

        assert response.status_code == 200
        data = response.get_json()
        assert "items" in data
        assert len(data["items"]) == 0

    def test_get_accounts_user_not_found(self, client):
        """Test getting accounts for non-existent user."""
        response = client.get('/plaid/accounts/99999')

        assert response.status_code == 404


class TestPlaidTransactions:
    """Test Plaid transactions retrieval."""

    def test_get_transactions_empty(self, client, sample_user_for_plaid):
        """Test getting transactions for user with no linked items."""
        response = client.get(f'/plaid/transactions/{sample_user_for_plaid}')

        assert response.status_code == 200
        data = response.get_json()
        assert data["transactions"] == []
        assert data["total"] == 0

    def test_get_transactions_with_date_filter(self, client, sample_user_for_plaid):
        """Test getting transactions with date filtering."""
        response = client.get(
            f'/plaid/transactions/{sample_user_for_plaid}',
            query_string={
                "startDate": "2026-01-01",
                "endDate": "2026-01-31",
                "limit": 50
            }
        )

        assert response.status_code == 200
        data = response.get_json()
        assert "transactions" in data
        assert "total" in data
        assert "hasMore" in data


class TestPlaidSync:
    """Test Plaid transaction sync."""

    def test_sync_no_linked_accounts(self, client, sample_user_for_plaid):
        """Test sync for user with no linked accounts."""
        response = client.post(f'/plaid/sync/{sample_user_for_plaid}')

        assert response.status_code == 404
        assert "No linked accounts found" in response.get_json()["error"]


class TestPlaidUnlink:
    """Test Plaid item unlinking."""

    def test_unlink_not_found(self, client, sample_user_for_plaid):
        """Test unlinking non-existent item."""
        response = client.delete(
            f'/plaid/unlink/{sample_user_for_plaid}/nonexistent-item-id'
        )

        assert response.status_code == 404
        assert "Plaid item not found" in response.get_json()["error"]
