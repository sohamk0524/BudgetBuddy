"""
Unit tests for models.py - Data models and response structures.
"""

import pytest
from models import (
    SankeyNode,
    BurndownDataPoint,
    VisualPayload,
    AssistantResponse
)


@pytest.mark.unit
class TestSankeyNode:
    """Tests for SankeyNode data class."""

    def test_sankey_node_creation(self):
        """Test creating a SankeyNode."""
        node = SankeyNode(id="income", name="Income", value=5000.0)
        assert node.id == "income"
        assert node.name == "Income"
        assert node.value == 5000.0

    def test_sankey_node_to_dict(self):
        """Test converting SankeyNode to dictionary."""
        node = SankeyNode(id="expenses", name="Expenses", value=2000.0)
        node_dict = node.to_dict()

        assert node_dict == {
            "id": "expenses",
            "name": "Expenses",
            "value": 2000.0
        }


@pytest.mark.unit
class TestBurndownDataPoint:
    """Tests for BurndownDataPoint data class."""

    def test_burndown_creation(self):
        """Test creating a BurndownDataPoint."""
        point = BurndownDataPoint(date="2024-01-01", amount=1000.0)
        assert point.date == "2024-01-01"
        assert point.amount == 1000.0

    def test_burndown_to_dict(self):
        """Test converting BurndownDataPoint to dictionary."""
        point = BurndownDataPoint(date="2024-01-15", amount=500.0)
        point_dict = point.to_dict()

        assert point_dict == {
            "date": "2024-01-15",
            "amount": 500.0
        }


@pytest.mark.unit
class TestVisualPayload:
    """Tests for VisualPayload helper class."""

    def test_burndown_chart_payload(self):
        """Test creating a burndown chart payload."""
        payload = VisualPayload.burndown_chart(
            spent=500.0,
            budget=1000.0,
            ideal_pace=750.0
        )

        assert payload["type"] == "burndownChart"
        assert payload["spent"] == 500.0
        assert payload["budget"] == 1000.0
        assert payload["idealPace"] == 750.0

    def test_sankey_flow_payload(self):
        """Test creating a sankey flow payload."""
        nodes = [
            SankeyNode(id="income", name="Income", value=5000.0),
            SankeyNode(id="expenses", name="Expenses", value=2000.0)
        ]

        payload = VisualPayload.sankey_flow(nodes)

        assert payload["type"] == "sankeyFlow"
        assert len(payload["nodes"]) == 2
        assert payload["nodes"][0]["id"] == "income"
        assert payload["nodes"][1]["value"] == 2000.0

    def test_interactive_slider_payload(self):
        """Test creating an interactive slider payload."""
        payload = VisualPayload.interactive_slider(
            category="Groceries",
            current=300.0,
            max_val=500.0
        )

        assert payload["type"] == "interactiveSlider"
        assert payload["category"] == "Groceries"
        assert payload["current"] == 300.0
        assert payload["max"] == 500.0

    def test_budget_slider_payload(self):
        """Test creating a budget slider payload."""
        payload = VisualPayload.budget_slider(
            category="Dining",
            current=150.0,
            max_val=300.0
        )

        assert payload["type"] == "budgetSlider"
        assert payload["category"] == "Dining"
        assert payload["current"] == 150.0
        assert payload["max"] == 300.0


@pytest.mark.unit
class TestAssistantResponse:
    """Tests for AssistantResponse data class."""

    def test_response_text_only(self):
        """Test creating a response with only text."""
        response = AssistantResponse(text_message="Hello!")

        assert response.text_message == "Hello!"
        assert response.visual_payload is None

    def test_response_with_visual(self):
        """Test creating a response with visual payload."""
        visual = VisualPayload.burndown_chart(
            spent=100.0,
            budget=500.0,
            ideal_pace=250.0
        )
        response = AssistantResponse(
            text_message="Here's your spending",
            visual_payload=visual
        )

        assert response.text_message == "Here's your spending"
        assert response.visual_payload is not None
        assert response.visual_payload["type"] == "burndownChart"

    def test_response_to_dict_text_only(self):
        """Test converting text-only response to dict."""
        response = AssistantResponse(text_message="Test message")
        response_dict = response.to_dict()

        assert response_dict["textMessage"] == "Test message"
        assert response_dict["visualPayload"] is None

    def test_response_to_dict_with_visual(self):
        """Test converting response with visual to dict."""
        nodes = [SankeyNode(id="test", name="Test", value=100.0)]
        visual = VisualPayload.sankey_flow(nodes)
        response = AssistantResponse(
            text_message="Your budget",
            visual_payload=visual
        )

        response_dict = response.to_dict()

        assert response_dict["textMessage"] == "Your budget"
        assert response_dict["visualPayload"]["type"] == "sankeyFlow"
        assert len(response_dict["visualPayload"]["nodes"]) == 1

    def test_response_camel_case_keys(self):
        """Test that to_dict uses camelCase keys for JSON serialization."""
        response = AssistantResponse(text_message="Test")
        response_dict = response.to_dict()

        # Should use camelCase, not snake_case
        assert "textMessage" in response_dict
        assert "text_message" not in response_dict
        assert "visualPayload" in response_dict
        assert "visual_payload" not in response_dict
