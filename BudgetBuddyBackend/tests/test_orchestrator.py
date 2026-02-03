"""
Unit tests for services/orchestrator.py - Main message processing orchestrator.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from services.orchestrator import (
    process_message,
    _should_use_tools,
    _extract_amount,
    _handle_personalized_query,
    _determine_visual_payload,
    _fallback_response
)
from models import AssistantResponse


@pytest.mark.unit
class TestShouldUseTools:
    """Tests for _should_use_tools function."""

    def test_finance_keywords_trigger_tools(self):
        """Test that finance-related keywords trigger tool usage."""
        assert _should_use_tools("Show me my budget") is True
        assert _should_use_tools("How much have I spent?") is True
        assert _should_use_tools("Can I afford this?") is True
        assert _should_use_tools("What's my account balance?") is True
        assert _should_use_tools("Show my savings progress") is True

    def test_greetings_dont_trigger_tools(self):
        """Test that greetings don't trigger tool usage."""
        assert _should_use_tools("Hello") is False
        assert _should_use_tools("Hi there") is False
        assert _should_use_tools("Hey") is False
        assert _should_use_tools("Good morning") is False

    def test_general_questions_dont_trigger_tools(self):
        """Test that general questions don't trigger tool usage."""
        assert _should_use_tools("What can you do?") is False
        assert _should_use_tools("Help me") is False
        assert _should_use_tools("How are you?") is False

    def test_case_insensitive_matching(self):
        """Test that keyword matching is case-insensitive."""
        assert _should_use_tools("BUDGET") is True
        assert _should_use_tools("SpEnDiNg") is True
        assert _should_use_tools("AFFORD") is True


@pytest.mark.unit
class TestExtractAmount:
    """Tests for _extract_amount function."""

    def test_extract_dollar_amount(self):
        """Test extracting dollar amounts from text."""
        assert _extract_amount("Can I afford $50?") == 50.0
        assert _extract_amount("I want to buy something for $150") == 150.0
        assert _extract_amount("$1,234.56 item") == 1234.56

    def test_extract_without_dollar_sign(self):
        """Test extracting amounts without dollar sign."""
        assert _extract_amount("Can I afford 75?") == 75.0
        assert _extract_amount("200 dollars") == 200.0

    def test_default_amount(self):
        """Test default amount when no number found."""
        assert _extract_amount("Can I afford this?") == 100.0
        assert _extract_amount("No numbers here") == 100.0

    def test_comma_separated_amounts(self):
        """Test extracting comma-separated amounts."""
        assert _extract_amount("$1,000 purchase") == 1000.0
        assert _extract_amount("$10,500.50") == 10500.50


@pytest.mark.unit
class TestHandlePersonalizedQuery:
    """Tests for _handle_personalized_query function."""

    @patch('services.orchestrator.get_user_profile')
    def test_afford_query_within_budget(self, mock_get_profile):
        """Test afford query when user can afford the item."""
        mock_get_profile.return_value = {
            "monthly_income": 5000,
            "fixed_expenses": 2000,
            "discretionary": 3000,
            "savings_goal_name": "Car",
            "savings_goal_target": 10000
        }

        response = _handle_personalized_query("Can I afford $500?", "user123")

        assert response is not None
        assert isinstance(response, AssistantResponse)
        assert "$500" in response.text_message
        assert "can afford" in response.text_message.lower()
        assert response.visual_payload is not None

    @patch('services.orchestrator.get_user_profile')
    def test_afford_query_exceeds_budget(self, mock_get_profile):
        """Test afford query when item exceeds budget."""
        mock_get_profile.return_value = {
            "monthly_income": 3000,
            "fixed_expenses": 2500,
            "discretionary": 500,
            "savings_goal_name": None,
            "savings_goal_target": 0
        }

        response = _handle_personalized_query("Can I afford $1000?", "user123")

        assert response is not None
        assert "exceed" in response.text_message.lower()
        assert response.visual_payload is not None

    @patch('services.orchestrator.get_user_profile')
    def test_plan_query(self, mock_get_profile):
        """Test plan-related query."""
        mock_get_profile.return_value = {
            "monthly_income": 5000,
            "fixed_expenses": 2000,
            "discretionary": 3000,
            "savings_goal_name": "Emergency Fund",
            "savings_goal_target": 5000
        }

        response = _handle_personalized_query("Show me my plan", "user123")

        assert response is not None
        assert "financial plan" in response.text_message.lower()
        assert response.visual_payload is not None
        assert response.visual_payload["type"] == "sankeyFlow"

    @patch('services.orchestrator.get_user_profile')
    def test_no_profile_returns_none(self, mock_get_profile):
        """Test that function returns None when user has no profile."""
        mock_get_profile.return_value = None

        response = _handle_personalized_query("Can I afford $100?", "user123")

        assert response is None

    @patch('services.orchestrator.get_user_profile')
    def test_unrecognized_query_returns_none(self, mock_get_profile):
        """Test that unrecognized queries return None."""
        mock_get_profile.return_value = {
            "monthly_income": 5000,
            "fixed_expenses": 2000,
            "discretionary": 3000,
            "savings_goal_name": None,
            "savings_goal_target": 0
        }

        response = _handle_personalized_query("Hello", "user123")

        assert response is None


@pytest.mark.unit
class TestDetermineVisualPayload:
    """Tests for _determine_visual_payload function."""

    def test_no_tools_returns_none(self):
        """Test that no tool results returns None."""
        payload = _determine_visual_payload([])
        assert payload is None

    def test_budget_overview_tool_result(self):
        """Test visual payload for budget overview tool."""
        tool_results = [{
            "tool": "get_budget_overview",
            "result": {
                "nodes": [
                    {"id": "income", "name": "Income", "value": 5000},
                    {"id": "expenses", "name": "Expenses", "value": 2000}
                ]
            }
        }]

        payload = _determine_visual_payload(tool_results)

        assert payload is not None
        assert payload["type"] == "sankeyFlow"
        assert len(payload["nodes"]) == 2

    def test_spending_status_tool_result(self):
        """Test visual payload for spending status tool."""
        tool_results = [{
            "tool": "get_spending_status",
            "result": {
                "spent": 500,
                "budget": 1000,
                "idealPace": 750
            }
        }]

        payload = _determine_visual_payload(tool_results)

        assert payload is not None
        assert payload["type"] == "burndownChart"
        assert payload["spent"] == 500
        assert payload["budget"] == 1000

    def test_multiple_tools_uses_first_relevant(self):
        """Test that multiple tool results use the first relevant one."""
        tool_results = [
            {"tool": "get_account_balance", "result": {"balance": 1000}},
            {"tool": "get_spending_status", "result": {"spent": 500, "budget": 1000, "idealPace": 750}}
        ]

        payload = _determine_visual_payload(tool_results)

        # Should use spending_status (first with visual)
        assert payload is not None
        assert payload["type"] == "burndownChart"


@pytest.mark.unit
class TestFallbackResponse:
    """Tests for _fallback_response function."""

    def test_fallback_with_error_message(self):
        """Test fallback with explicit error message."""
        response = _fallback_response("Test", "Custom error message")

        assert isinstance(response, AssistantResponse)
        assert response.text_message == "Custom error message"
        assert response.visual_payload is None

    def test_fallback_for_greeting(self):
        """Test fallback response for greetings."""
        response = _fallback_response("Hello", None)

        assert "BudgetBuddy" in response.text_message
        assert response.visual_payload is None

    def test_fallback_for_budget_query(self):
        """Test fallback response for budget queries."""
        response = _fallback_response("Show my budget overview", None)

        assert response.visual_payload is not None
        assert response.visual_payload["type"] == "sankeyFlow"

    def test_fallback_for_spending_query(self):
        """Test fallback response for spending queries."""
        response = _fallback_response("Can I afford that?", None)

        assert response.visual_payload is not None
        assert response.visual_payload["type"] == "burndownChart"


@pytest.mark.unit
@patch('services.orchestrator.agent')
class TestProcessMessage:
    """Tests for process_message function."""

    def test_process_greeting_without_tools(self, mock_agent):
        """Test processing a simple greeting."""
        mock_agent.is_available.return_value = True
        mock_agent.chat.return_value = Mock(
            choices=[Mock(message=Mock(content="Hello! How can I help?"))]
        )

        response = process_message("Hi", "user123")

        assert isinstance(response, AssistantResponse)
        assert "Hello" in response.text_message
        mock_agent.chat.assert_called_once()

    def test_process_message_when_ollama_unavailable(self, mock_agent):
        """Test processing message when Ollama is not available."""
        mock_agent.is_available.return_value = False

        response = process_message("Show my budget", "user123")

        assert isinstance(response, AssistantResponse)
        assert "Ollama" in response.text_message or "AI" in response.text_message

    @patch('services.orchestrator._handle_personalized_query')
    def test_uses_personalized_query_first(self, mock_personalized, mock_agent):
        """Test that personalized query is checked first."""
        mock_personalized.return_value = AssistantResponse(
            text_message="Personalized response"
        )

        response = process_message("Can I afford $100?", "user123")

        assert response.text_message == "Personalized response"
        mock_personalized.assert_called_once()
        mock_agent.is_available.assert_not_called()

    def test_process_finance_query_with_tools(self, mock_agent):
        """Test processing finance query that uses tools."""
        mock_agent.is_available.return_value = True
        mock_agent.chat_with_tools.return_value = {
            "content": "You've spent $500 of your $1000 budget.",
            "tool_results": [{
                "tool": "get_spending_status",
                "result": {"spent": 500, "budget": 1000, "idealPace": 750}
            }]
        }

        response = process_message("How much have I spent?", "user123")

        assert isinstance(response, AssistantResponse)
        assert response.visual_payload is not None
        mock_agent.chat_with_tools.assert_called_once()


@pytest.mark.unit
class TestGetUserProfile:
    """Tests for get_user_profile function."""

    def test_get_existing_profile(self, app, sample_user_with_profile):
        """Test getting an existing user profile."""
        from services.orchestrator import get_user_profile

        with app.app_context():
            profile = get_user_profile(sample_user_with_profile)

            assert profile is not None
            assert "monthly_income" in profile
            assert "discretionary" in profile
            assert profile["monthly_income"] == 5000.0

    def test_get_profile_user_not_found(self, app):
        """Test getting profile for non-existent user."""
        from services.orchestrator import get_user_profile

        with app.app_context():
            profile = get_user_profile(99999)

            assert profile is None

    def test_get_profile_no_profile(self, app, sample_user):
        """Test getting profile for user without profile."""
        from services.orchestrator import get_user_profile

        with app.app_context():
            profile = get_user_profile(sample_user)

            # User exists but has no profile
            assert profile is None
