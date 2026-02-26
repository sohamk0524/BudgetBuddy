"""
LLM Service - Agent class for BudgetBuddy.
Uses LiteLLM to route to Claude (or any other provider).
"""

import json
import litellm
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field


@dataclass
class Agent:
    """
    Declarative AI agent powered by LiteLLM.

    Usage:
        agent = Agent(
            name="BudgetBuddy",
            instructions=system_prompt,
            tools=get_tools(),
            model="claude-sonnet-4-5-20250929",
            tool_executor=execute_tool,
        )
        result = agent.run("What's my budget?")
    """
    name: str
    instructions: str
    model: str = "claude-sonnet-4-5-20250929"
    tools: Optional[List[Dict[str, Any]]] = None
    tool_executor: Optional[Callable[[str, Dict], Any]] = None
    max_iterations: int = 5

    def run(self, user_message: str) -> Dict[str, Any]:
        """
        Run the agent with a user message.
        Handles the tool-calling loop automatically.

        Returns:
            Dict with 'content' (response text) and 'tool_results' (list of tool calls made)
        """
        messages = [{"role": "user", "content": user_message}]
        return self._execute(messages)

    def run_with_messages(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Run with a custom message list (system prompt is still prepended).

        Returns:
            Dict with 'content' (response text) and 'tool_results' (list of tool calls made)
        """
        return self._execute(messages)

    def _execute(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Core execution loop with tool calling."""
        conversation = [
            {"role": "system", "content": self.instructions}
        ] + messages
        all_tool_results = []

        for _ in range(self.max_iterations):
            kwargs = {"model": self.model, "messages": conversation}
            if self.tools:
                kwargs["tools"] = self.tools
                kwargs["tool_choice"] = "auto"

            response = litellm.completion(**kwargs)
            message = response.choices[0].message

            # No tool calls — return the text response
            if not message.tool_calls:
                return {
                    "content": message.content or "",
                    "tool_results": all_tool_results
                }

            # Add assistant message with tool calls to conversation
            conversation.append(message.model_dump())

            # Execute each tool call
            for tool_call in message.tool_calls:
                tool_name = tool_call.function.name
                try:
                    tool_args = json.loads(tool_call.function.arguments) if tool_call.function.arguments else {}
                except json.JSONDecodeError:
                    tool_args = {}

                try:
                    result = self.tool_executor(tool_name, tool_args)
                    all_tool_results.append({
                        "tool": tool_name,
                        "args": tool_args,
                        "result": result
                    })
                    conversation.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(result) if isinstance(result, dict) else str(result)
                    })
                except Exception as e:
                    conversation.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps({"error": str(e)})
                    })

        # Max iterations reached — get final response without tools
        response = litellm.completion(model=self.model, messages=conversation)
        return {
            "content": response.choices[0].message.content or "",
            "tool_results": all_tool_results
        }

    def is_available(self) -> bool:
        """Check if the LLM provider is reachable."""
        try:
            litellm.completion(
                model=self.model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=5
            )
            return True
        except Exception:
            return False
