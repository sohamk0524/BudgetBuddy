"""
Unit tests for services/llm_service.py - LLM service wrapper.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from services.llm_service import (
    BudgetBuddyAgent,
    OllamaError,
    OllamaConnectionError
)


@pytest.mark.unit
class TestBudgetBuddyAgent:
    """Tests for BudgetBuddyAgent class."""

    def test_agent_initialization(self):
        """Test creating a BudgetBuddyAgent instance."""
        agent = BudgetBuddyAgent(model="llama3.2:3b")

        assert agent.model == "llama3.2:3b"
        assert agent.client is not None

    def test_agent_custom_base_url(self):
        """Test creating agent with custom base URL."""
        custom_url = "http://custom:8080/v1"
        agent = BudgetBuddyAgent(base_url=custom_url, model="test-model")

        assert agent.model == "test-model"

    @patch('services.llm_service.OpenAI')
    def test_chat_without_tools(self, mock_openai):
        """Test chat method without tools."""
        mock_client = Mock()
        mock_openai.return_value = mock_client

        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="Hello!"))]
        mock_client.chat.completions.create.return_value = mock_response

        agent = BudgetBuddyAgent()
        messages = [{"role": "user", "content": "Hi"}]

        response = agent.chat(messages)

        assert response.choices[0].message.content == "Hello!"
        mock_client.chat.completions.create.assert_called_once()

    @patch('services.llm_service.OpenAI')
    def test_chat_with_tools(self, mock_openai):
        """Test chat method with tools."""
        mock_client = Mock()
        mock_openai.return_value = mock_client

        mock_response = Mock()
        mock_client.chat.completions.create.return_value = mock_response

        agent = BudgetBuddyAgent()
        messages = [{"role": "user", "content": "Show budget"}]
        tools = [{"type": "function", "function": {"name": "test_tool"}}]

        agent.chat(messages, tools=tools)

        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert "tools" in call_kwargs
        assert call_kwargs["tools"] == tools
        assert call_kwargs["tool_choice"] == "auto"

    @patch('services.llm_service.OpenAI')
    def test_chat_with_tools_execution(self, mock_openai):
        """Test chat_with_tools method with tool execution."""
        mock_client = Mock()
        mock_openai.return_value = mock_client

        # First call: model wants to use tool
        mock_tool_call = Mock()
        mock_tool_call.id = "call_123"
        mock_tool_call.function.name = "test_tool"
        mock_tool_call.function.arguments = "{}"

        mock_response1 = Mock()
        mock_response1.choices = [Mock(message=Mock(
            content="",
            tool_calls=[mock_tool_call]
        ))]

        # Second call: model returns final response
        mock_response2 = Mock()
        mock_response2.choices = [Mock(message=Mock(
            content="Here's your result",
            tool_calls=None
        ))]

        mock_client.chat.completions.create.side_effect = [
            mock_response1,
            mock_response2
        ]

        agent = BudgetBuddyAgent()
        messages = [{"role": "user", "content": "Test"}]
        tools = [{"type": "function", "function": {"name": "test_tool"}}]

        def mock_executor(name, args):
            return {"result": "success"}

        result = agent.chat_with_tools(messages, tools, mock_executor)

        assert result["content"] == "Here's your result"
        assert len(result["tool_results"]) == 1
        assert result["tool_results"][0]["tool"] == "test_tool"

    @patch('services.llm_service.OpenAI')
    def test_chat_with_tools_max_iterations(self, mock_openai):
        """Test that chat_with_tools respects max_iterations."""
        mock_client = Mock()
        mock_openai.return_value = mock_client

        # Always return tool calls
        mock_tool_call = Mock()
        mock_tool_call.id = "call_123"
        mock_tool_call.function.name = "test_tool"
        mock_tool_call.function.arguments = "{}"

        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(
            content="",
            tool_calls=[mock_tool_call]
        ))]

        # Final response after max iterations
        mock_final_response = Mock()
        mock_final_response.choices = [Mock(message=Mock(
            content="Done",
            tool_calls=None
        ))]

        mock_client.chat.completions.create.side_effect = [
            mock_response,
            mock_response,
            mock_response,
            mock_final_response
        ]

        agent = BudgetBuddyAgent()
        messages = [{"role": "user", "content": "Test"}]
        tools = [{"type": "function", "function": {"name": "test_tool"}}]

        def mock_executor(name, args):
            return {"result": "success"}

        result = agent.chat_with_tools(
            messages,
            tools,
            mock_executor,
            max_iterations=3
        )

        # Should have called tool 3 times, then final response
        assert len(result["tool_results"]) == 3
        assert mock_client.chat.completions.create.call_count == 4

    @patch('services.llm_service.OpenAI')
    def test_is_available_success(self, mock_openai):
        """Test is_available when Ollama is running."""
        mock_client = Mock()
        mock_openai.return_value = mock_client
        mock_client.models.list.return_value = []

        agent = BudgetBuddyAgent()
        assert agent.is_available() is True

    @patch('services.llm_service.OpenAI')
    def test_is_available_failure(self, mock_openai):
        """Test is_available when Ollama is not running."""
        mock_client = Mock()
        mock_openai.return_value = mock_client
        mock_client.models.list.side_effect = Exception("Connection failed")

        agent = BudgetBuddyAgent()
        assert agent.is_available() is False

    @patch('services.llm_service.OpenAI')
    def test_tool_execution_error_handling(self, mock_openai):
        """Test that tool execution errors are handled gracefully."""
        mock_client = Mock()
        mock_openai.return_value = mock_client

        # Model wants to use tool
        mock_tool_call = Mock()
        mock_tool_call.id = "call_123"
        mock_tool_call.function.name = "test_tool"
        mock_tool_call.function.arguments = "{}"

        mock_response1 = Mock()
        mock_response1.choices = [Mock(message=Mock(
            content="",
            tool_calls=[mock_tool_call]
        ))]

        # Final response
        mock_response2 = Mock()
        mock_response2.choices = [Mock(message=Mock(
            content="Error handled",
            tool_calls=None
        ))]

        mock_client.chat.completions.create.side_effect = [
            mock_response1,
            mock_response2
        ]

        agent = BudgetBuddyAgent()
        messages = [{"role": "user", "content": "Test"}]
        tools = [{"type": "function", "function": {"name": "test_tool"}}]

        def failing_executor(name, args):
            raise Exception("Tool failed")

        result = agent.chat_with_tools(messages, tools, failing_executor)

        # Should still return a result
        assert "content" in result
        assert result["content"] == "Error handled"


@pytest.mark.unit
class TestExceptionClasses:
    """Tests for custom exception classes."""

    def test_ollama_error(self):
        """Test OllamaError exception."""
        error = OllamaError("Test error")
        assert str(error) == "Test error"
        assert isinstance(error, Exception)

    def test_ollama_connection_error(self):
        """Test OllamaConnectionError exception."""
        error = OllamaConnectionError("Connection failed")
        assert str(error) == "Connection failed"
        assert isinstance(error, OllamaError)
