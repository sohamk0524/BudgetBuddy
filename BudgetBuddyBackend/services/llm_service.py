"""
LLM Service - OpenAI SDK client for BudgetBuddy.
Uses Ollama's OpenAI-compatible endpoint for local LLM inference.
"""

import json
from typing import List, Dict, Any, Optional, Callable
from openai import OpenAI


class BudgetBuddyAgent:
    """
    AI Agent using OpenAI SDK with Ollama backend.
    Provides clean tool calling and conversation handling.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:11434/v1",
        model: str = "llama3.2:3b"
    ):
        self.client = OpenAI(
            base_url=base_url,
            api_key="ollama"  # Ollama doesn't require a real API key
        )
        self.model = model

    def chat(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None
    ):
        """
        Send a chat request to the LLM.

        Args:
            messages: List of message dicts with 'role' and 'content'
            tools: Optional list of tool definitions

        Returns:
            OpenAI ChatCompletion response
        """
        kwargs = {
            "model": self.model,
            "messages": messages,
        }

        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"  # Let model decide when to use tools

        return self.client.chat.completions.create(**kwargs)

    def chat_with_tools(
        self,
        messages: List[Dict[str, str]],
        tools: List[Dict[str, Any]],
        tool_executor: Callable[[str, Dict], Any],
        max_iterations: int = 3
    ) -> Dict[str, Any]:
        """
        Chat with automatic tool execution.

        Args:
            messages: Initial conversation messages
            tools: List of tool definitions
            tool_executor: Function to execute tools: (name, args) -> result
            max_iterations: Max tool call iterations

        Returns:
            Dict with 'content' (response text) and 'tool_results' (list of tool calls made)
        """
        conversation = messages.copy()
        all_tool_results = []

        for _ in range(max_iterations):
            response = self.chat(conversation, tools=tools)
            message = response.choices[0].message

            # Check if model wants to call tools
            if not message.tool_calls:
                # No tool calls - return the response
                return {
                    "content": message.content or "",
                    "tool_results": all_tool_results
                }

            # Add assistant message with tool calls to conversation
            conversation.append({
                "role": "assistant",
                "content": message.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    }
                    for tc in message.tool_calls
                ]
            })

            # Execute each tool call
            for tool_call in message.tool_calls:
                tool_name = tool_call.function.name
                try:
                    tool_args = json.loads(tool_call.function.arguments) if tool_call.function.arguments else {}
                except json.JSONDecodeError:
                    tool_args = {}

                # Execute the tool
                try:
                    result = tool_executor(tool_name, tool_args)
                    all_tool_results.append({
                        "tool": tool_name,
                        "args": tool_args,
                        "result": result
                    })

                    # Add tool result to conversation
                    conversation.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(result) if isinstance(result, dict) else str(result)
                    })

                except Exception as e:
                    # Tool execution failed
                    conversation.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps({"error": str(e)})
                    })

        # Max iterations reached, get final response without tools
        response = self.chat(conversation, tools=None)
        return {
            "content": response.choices[0].message.content or "",
            "tool_results": all_tool_results
        }

    def is_available(self) -> bool:
        """Check if the Ollama server is accessible."""
        try:
            # Try a simple models list call
            self.client.models.list()
            return True
        except Exception:
            return False


# Backwards compatibility aliases
class OllamaClient(BudgetBuddyAgent):
    """Alias for backwards compatibility."""
    pass


class OllamaError(Exception):
    """Base exception for Ollama errors."""
    pass


class OllamaConnectionError(OllamaError):
    """Raised when cannot connect to Ollama."""
    pass


class OllamaTimeoutError(OllamaError):
    """Raised when Ollama request times out."""
    pass


# Default agent instance
default_agent = BudgetBuddyAgent()
