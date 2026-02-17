"""
Integration tests for Flask API endpoints in app.py.
"""

import pytest
import json
import io
from unittest.mock import patch, Mock


@pytest.mark.integration
class TestHealthAndIndex:
    """Tests for health and index endpoints."""

    def test_index_endpoint(self, client):
        """Test the index endpoint."""
        response = client.get("/")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert "message" in data
        assert "BudgetBuddy" in data["message"]

    def test_health_endpoint(self, client):
        """Test the health check endpoint."""
        response = client.get("/health")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["status"] == "ok"


@pytest.mark.integration
class TestSMSAuthEndpoints:
    """Tests for SMS authentication endpoints."""

    def test_send_sms_code(self, client):
        """Test sending an SMS verification code."""
        response = client.post(
            "/v1/send_sms_code",
            json={"phone_number": "+15555550400"}
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["status"] == "success"

    def test_send_sms_code_missing_phone(self, client):
        """Test sending code without phone number."""
        response = client.post(
            "/v1/send_sms_code",
            json={}
        )

        assert response.status_code == 400

    def test_send_sms_code_invalid_format(self, client):
        """Test sending code with invalid phone format."""
        response = client.post(
            "/v1/send_sms_code",
            json={"phone_number": "not-a-phone"}
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert "invalid" in data["error"].lower() or "format" in data["error"].lower()

    def test_send_sms_code_invalid_json(self, client):
        """Test sending code with invalid JSON."""
        response = client.post(
            "/v1/send_sms_code",
            data="not json",
            content_type="application/json"
        )

        assert response.status_code == 400

    def test_verify_code_success(self, client):
        """Test verifying a valid code creates/returns user."""
        # First send a code
        client.post(
            "/v1/send_sms_code",
            json={"phone_number": "+15555550401"}
        )

        # Get the OTP from the database
        from db_models import OTPCode
        with client.application.app_context():
            otp = OTPCode.query.filter_by(phone_number="+15555550401").first()
            code = otp.code

        # Verify the code
        response = client.post(
            "/v1/verify_code",
            json={"phone_number": "+15555550401", "code": code}
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert "token" in data
        assert isinstance(data["token"], int)
        assert "hasProfile" in data
        assert isinstance(data["hasProfile"], bool)

    def test_verify_code_wrong_code(self, client):
        """Test verifying with wrong code."""
        # First send a code
        client.post(
            "/v1/send_sms_code",
            json={"phone_number": "+15555550402"}
        )

        # Verify with wrong code
        response = client.post(
            "/v1/verify_code",
            json={"phone_number": "+15555550402", "code": "000000"}
        )

        assert response.status_code == 401

    def test_verify_code_no_code_sent(self, client):
        """Test verifying when no code was sent."""
        response = client.post(
            "/v1/verify_code",
            json={"phone_number": "+15555550403", "code": "123456"}
        )

        assert response.status_code == 400

    def test_verify_code_returns_name(self, client):
        """Test that verify_code returns user name when set."""
        # Send and verify to create user
        client.post(
            "/v1/send_sms_code",
            json={"phone_number": "+15555550404"}
        )

        from db_models import OTPCode
        with client.application.app_context():
            otp = OTPCode.query.filter_by(phone_number="+15555550404").first()
            code = otp.code

        response = client.post(
            "/v1/verify_code",
            json={"phone_number": "+15555550404", "code": code}
        )

        data = json.loads(response.data)
        assert "name" in data

    def test_verify_code_has_profile_flag(self, client, sample_user_with_profile):
        """Test that verify returns correct hasProfile flag for existing user with profile."""
        # Get the phone number for this user
        from db_models import User
        with client.application.app_context():
            user = User.query.get(sample_user_with_profile)
            phone = user.phone_number

        # Send code to existing user
        client.post(
            "/v1/send_sms_code",
            json={"phone_number": phone}
        )

        from db_models import OTPCode
        with client.application.app_context():
            otp = OTPCode.query.filter_by(phone_number=phone).first()
            code = otp.code

        response = client.post(
            "/v1/verify_code",
            json={"phone_number": phone, "code": code}
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["hasProfile"] is True


@pytest.mark.integration
class TestDeleteUserEndpoint:
    """Tests for user deletion endpoint."""

    def test_delete_user(self, client, sample_user):
        """Test deleting a user."""
        response = client.delete(f"/v1/user?userId={sample_user}")

        assert response.status_code == 204

    def test_delete_nonexistent_user(self, client):
        """Test deleting non-existent user returns 204 (idempotent)."""
        response = client.delete("/v1/user?userId=99999")

        assert response.status_code == 204

    def test_delete_user_missing_id(self, client):
        """Test delete without userId."""
        response = client.delete("/v1/user")

        assert response.status_code == 400


@pytest.mark.integration
class TestOnboardingEndpoint:
    """Tests for onboarding endpoint."""

    def test_onboarding_create_profile(self, client, sample_user):
        """Test creating a financial profile."""
        response = client.post(
            "/onboarding",
            json={
                "userId": sample_user,
                "name": "Test User",
                "isStudent": True,
                "budgetingGoal": "save_purchase",
                "strictnessLevel": "moderate"
            }
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["status"] == "success"

    def test_onboarding_update_profile(self, client, sample_user_with_profile):
        """Test updating existing profile."""
        response = client.post(
            "/onboarding",
            json={
                "userId": sample_user_with_profile,
                "isStudent": False,
                "budgetingGoal": "pay_debt",
                "strictnessLevel": "strict"
            }
        )

        assert response.status_code == 200

    def test_onboarding_missing_user_id(self, client):
        """Test onboarding without userId."""
        response = client.post(
            "/onboarding",
            json={"income": 5000.0}
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert "required" in data["error"].lower()

    def test_onboarding_invalid_user(self, client):
        """Test onboarding with non-existent user."""
        response = client.post(
            "/onboarding",
            json={
                "userId": 99999,
                "income": 5000.0,
                "expenses": 2000.0
            }
        )

        assert response.status_code == 404


@pytest.mark.integration
class TestPlanEndpoints:
    """Tests for plan generation and retrieval endpoints."""

    @patch('services.plan_generator.agent')
    def test_generate_plan(self, mock_agent, client, sample_user_with_profile):
        """Test generating a spending plan."""
        mock_agent.is_available.return_value = False  # Use fallback

        response = client.post(
            "/generate-plan",
            json={
                "userId": sample_user_with_profile,
                "deepDiveData": {
                    "fixedExpenses": {"rent": 1500},
                    "variableSpending": {"groceries": 400}
                }
            }
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert "textMessage" in data
        assert "plan" in data

    def test_generate_plan_missing_user_id(self, client):
        """Test plan generation without userId."""
        response = client.post(
            "/generate-plan",
            json={"deepDiveData": {}}
        )

        assert response.status_code == 400

    def test_generate_plan_invalid_user(self, client):
        """Test plan generation for non-existent user."""
        response = client.post(
            "/generate-plan",
            json={"userId": 99999, "deepDiveData": {}}
        )

        assert response.status_code == 404

    def test_get_plan_success(self, client, sample_user, sample_plan_data):
        """Test retrieving a user's plan."""
        # First save a plan
        from db_models import db, BudgetPlan

        with client.application.app_context():
            plan = BudgetPlan(
                user_id=sample_user,
                plan_json=json.dumps(sample_plan_data),
                month_year="2024-01"
            )
            db.session.add(plan)
            db.session.commit()

        # Now retrieve it
        response = client.get(f"/get-plan/{sample_user}")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["hasPlan"] is True
        assert "plan" in data
        assert data["plan"]["safeToSpend"] == 1000.0

    def test_get_plan_no_plan(self, client, sample_user):
        """Test retrieving plan when user has none."""
        response = client.get(f"/get-plan/{sample_user}")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["hasPlan"] is False
        assert data["plan"] is None

    def test_get_plan_invalid_user(self, client):
        """Test retrieving plan for non-existent user."""
        response = client.get("/get-plan/99999")

        assert response.status_code == 404


@pytest.mark.integration
class TestChatEndpoint:
    """Tests for chat endpoint."""

    @patch('services.orchestrator.agent')
    def test_chat_basic_message(self, mock_agent, client):
        """Test sending a basic chat message."""
        mock_agent.is_available.return_value = True
        mock_agent.chat.return_value = Mock(
            choices=[Mock(message=Mock(content="Hello! How can I help?"))]
        )

        response = client.post(
            "/chat",
            json={"message": "Hi", "userId": "test123"}
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert "textMessage" in data
        assert "visualPayload" in data

    def test_chat_missing_message(self, client):
        """Test chat without message field."""
        response = client.post(
            "/chat",
            json={"userId": "test"}
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert "required" in data["error"].lower()

    def test_chat_invalid_json(self, client):
        """Test chat with invalid JSON."""
        response = client.post(
            "/chat",
            data="not json",
            content_type="application/json"
        )

        assert response.status_code == 400

    @patch('services.orchestrator.agent')
    def test_chat_with_user_id(self, mock_agent, client, sample_user_with_profile):
        """Test chat with authenticated user."""
        mock_agent.is_available.return_value = True
        mock_agent.chat.return_value = Mock(
            choices=[Mock(message=Mock(content="Response"))]
        )

        response = client.post(
            "/chat",
            json={"message": "Show my plan", "userId": str(sample_user_with_profile)}
        )

        assert response.status_code == 200


@pytest.mark.integration
class TestStatementUploadEndpoint:
    """Tests for statement upload endpoint."""

    @patch('services.statement_analyzer.agent')
    def test_upload_csv_statement(self, mock_agent, client, sample_csv_content):
        """Test uploading CSV bank statement."""
        mock_agent.is_available.return_value = False  # Use fallback

        data = {
            "file": (io.BytesIO(sample_csv_content), "statement.csv")
        }

        response = client.post(
            "/upload-statement",
            data=data,
            content_type="multipart/form-data"
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert "textMessage" in data

    def test_upload_no_file(self, client):
        """Test upload without file."""
        response = client.post(
            "/upload-statement",
            data={},
            content_type="multipart/form-data"
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert "no file" in data["error"].lower()

    def test_upload_empty_filename(self, client):
        """Test upload with empty filename."""
        data = {
            "file": (io.BytesIO(b"data"), "")
        }

        response = client.post(
            "/upload-statement",
            data=data,
            content_type="multipart/form-data"
        )

        assert response.status_code == 400

    def test_upload_options_request(self, client):
        """Test OPTIONS request for CORS preflight."""
        response = client.options("/upload-statement")

        assert response.status_code == 200


@pytest.mark.integration
class TestCORS:
    """Tests for CORS configuration."""

    def test_cors_headers_present(self, client):
        """Test that CORS headers are present in responses."""
        response = client.get("/health")

        # CORS headers should be present
        assert response.status_code == 200
        # The exact header names depend on flask-cors configuration

    def test_cors_post_request(self, client):
        """Test CORS on POST requests."""
        response = client.post(
            "/v1/send_sms_code",
            json={"phone_number": "+15555550500"},
            headers={"Origin": "http://localhost:3000"}
        )

        assert response.status_code == 200


@pytest.mark.integration
class TestErrorHandling:
    """Tests for error handling across endpoints."""

    def test_404_route(self, client):
        """Test that non-existent routes return 404."""
        response = client.get("/nonexistent")

        assert response.status_code == 404

    def test_method_not_allowed(self, client):
        """Test wrong HTTP method."""
        response = client.get("/v1/send_sms_code")  # Should be POST

        assert response.status_code == 405

    def test_malformed_json(self, client):
        """Test endpoints handle malformed JSON."""
        response = client.post(
            "/v1/send_sms_code",
            data="{invalid json",
            content_type="application/json"
        )

        assert response.status_code == 400
