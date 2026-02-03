"""
Unit tests for services/tools.py - Tool definitions and execution.
"""

import pytest
from services.tools import (
    TOOL_DEFINITIONS,
    TOOL_EXECUTORS,
    execute_tool,
    get_tool_definitions,
    get_visual_type_for_tool
)


@pytest.mark.unit
class TestToolDefinitions:
    """Tests for tool definitions."""

    def test_tool_definitions_structure(self):
        """Test that tool definitions have correct structure."""
        assert isinstance(TOOL_DEFINITIONS, list)
        assert len(TOOL_DEFINITIONS) > 0

        for tool in TOOL_DEFINITIONS:
            assert "type" in tool
            assert tool["type"] == "function"
            assert "function" in tool
            assert "name" in tool["function"]
            assert "description" in tool["function"]
            assert "parameters" in tool["function"]

    def test_get_tool_definitions(self):
        """Test get_tool_definitions returns the correct list."""
        tools = get_tool_definitions()
        assert tools == TOOL_DEFINITIONS
        assert len(tools) == 4  # Should have 4 tools

    def test_tool_names(self):
        """Test that expected tools are defined."""
        tool_names = [tool["function"]["name"] for tool in TOOL_DEFINITIONS]

        assert "get_budget_overview" in tool_names
        assert "get_spending_status" in tool_names
        assert "get_account_balance" in tool_names
        assert "get_savings_progress" in tool_names

    def test_tool_descriptions_have_guidance(self):
        """Test that tool descriptions include usage guidance."""
        for tool in TOOL_DEFINITIONS:
            description = tool["function"]["description"]

            # Should mention when to use the tool
            assert "ONLY" in description or "when" in description.lower()


@pytest.mark.unit
class TestToolExecutors:
    """Tests for tool executors."""

    def test_executor_registry_completeness(self):
        """Test that all defined tools have executors."""
        tool_names = [tool["function"]["name"] for tool in TOOL_DEFINITIONS]

        for tool_name in tool_names:
            assert tool_name in TOOL_EXECUTORS

    def test_get_budget_overview_executor(self):
        """Test executing get_budget_overview tool."""
        result = execute_tool("get_budget_overview", {})

        assert "nodes" in result
        assert isinstance(result["nodes"], list)
        assert len(result["nodes"]) > 0

        # Check node structure
        first_node = result["nodes"][0]
        assert "id" in first_node
        assert "name" in first_node
        assert "value" in first_node

    def test_get_spending_status_executor(self):
        """Test executing get_spending_status tool."""
        result = execute_tool("get_spending_status", {})

        assert "spent" in result
        assert "budget" in result
        assert "idealPace" in result
        assert isinstance(result["spent"], (int, float))
        assert isinstance(result["budget"], (int, float))

    def test_get_account_balance_executor(self):
        """Test executing get_account_balance tool."""
        result = execute_tool("get_account_balance", {})

        assert "checking_balance" in result
        assert "savings_balance" in result
        assert "total_liquid" in result
        assert isinstance(result["checking_balance"], (int, float))

    def test_get_savings_progress_executor(self):
        """Test executing get_savings_progress tool."""
        result = execute_tool("get_savings_progress", {})

        assert "goals" in result
        assert "total_saved" in result
        assert "total_target" in result
        assert "overall_progress" in result
        assert isinstance(result["goals"], list)

    def test_execute_tool_with_invalid_name(self):
        """Test that executing unknown tool raises ValueError."""
        with pytest.raises(ValueError, match="Unknown tool"):
            execute_tool("nonexistent_tool", {})

    def test_execute_tool_with_arguments(self):
        """Test that tools can be executed with arguments."""
        # Even though these tools don't use arguments, they should accept them
        result = execute_tool("get_budget_overview", {"unused": "arg"})
        assert "nodes" in result


@pytest.mark.unit
class TestVisualTypeMapping:
    """Tests for visual type mapping."""

    def test_get_visual_type_for_tool(self):
        """Test getting visual type for each tool."""
        assert get_visual_type_for_tool("get_budget_overview") == "sankeyFlow"
        assert get_visual_type_for_tool("get_spending_status") == "burndownChart"
        assert get_visual_type_for_tool("get_account_balance") is None
        assert get_visual_type_for_tool("get_savings_progress") is None

    def test_get_visual_type_unknown_tool(self):
        """Test getting visual type for unknown tool returns None."""
        assert get_visual_type_for_tool("unknown_tool") is None


@pytest.mark.unit
class TestToolOutputFormats:
    """Tests for tool output data formats."""

    def test_budget_overview_output_format(self):
        """Test that budget overview returns properly formatted data."""
        result = execute_tool("get_budget_overview", {})

        # Should have nodes array
        assert "nodes" in result
        nodes = result["nodes"]

        # Each node should have required fields
        for node in nodes:
            assert isinstance(node, dict)
            assert "id" in node
            assert "name" in node
            assert "value" in node
            assert isinstance(node["value"], (int, float))
            assert node["value"] >= 0

    def test_spending_status_output_format(self):
        """Test that spending status returns properly formatted data."""
        result = execute_tool("get_spending_status", {})

        # Should have spending metrics
        assert "spent" in result
        assert "budget" in result
        assert "idealPace" in result

        # Values should be non-negative
        assert result["spent"] >= 0
        assert result["budget"] >= 0
        assert result["idealPace"] >= 0

        # Spent should not exceed budget in mock data
        assert result["spent"] <= result["budget"]

    def test_account_balance_output_format(self):
        """Test that account balance returns properly formatted data."""
        result = execute_tool("get_account_balance", {})

        assert "checking_balance" in result
        assert "savings_balance" in result
        assert "total_liquid" in result

        # Balances should be reasonable
        assert isinstance(result["checking_balance"], (int, float))
        assert isinstance(result["savings_balance"], (int, float))
        assert result["total_liquid"] == result["checking_balance"] + result["savings_balance"]

    def test_savings_progress_output_format(self):
        """Test that savings progress returns properly formatted data."""
        result = execute_tool("get_savings_progress", {})

        assert "goals" in result
        assert "overall_progress" in result
        assert isinstance(result["goals"], list)

        # Overall progress should be 0-100
        assert 0 <= result["overall_progress"] <= 100

        # Each goal should have proper structure
        for goal in result["goals"]:
            assert "name" in goal
            assert "current" in goal
            assert "target" in goal
            assert "progress_percent" in goal
