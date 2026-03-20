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
    response_format: Optional[Dict[str, Any]] = None

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

        print(f"[{self.name}] Starting agent run (model={self.model}, max_iterations={self.max_iterations})")

        for iteration in range(self.max_iterations):
            kwargs = {"model": self.model, "messages": conversation}
            if self.tools:
                kwargs["tools"] = self.tools
                kwargs["tool_choice"] = "auto"
            if self.response_format:
                kwargs["response_format"] = self.response_format

            print(f"[{self.name}] Iteration {iteration + 1}/{self.max_iterations} — calling LLM...")
            response = litellm.completion(**kwargs)
            message = response.choices[0].message

            # No tool calls — return the text response
            if not message.tool_calls:
                print(f"[{self.name}] LLM returned final text response ({len(message.content or '')} chars)")
                return {
                    "content": message.content or "",
                    "tool_results": all_tool_results
                }

            # Add assistant message with tool calls to conversation
            conversation.append(message.model_dump())

            print(f"[{self.name}] LLM requested {len(message.tool_calls)} tool call(s): {[tc.function.name for tc in message.tool_calls]}")

            # Execute each tool call
            for tool_call in message.tool_calls:
                tool_name = tool_call.function.name
                try:
                    tool_args = json.loads(tool_call.function.arguments) if tool_call.function.arguments else {}
                except json.JSONDecodeError:
                    tool_args = {}

                print(f"[{self.name}] Executing tool: {tool_name}({tool_args})")

                try:
                    result = self.tool_executor(tool_name, tool_args)
                    result_str = json.dumps(result) if isinstance(result, dict) else str(result)
                    print(f"[{self.name}] Tool {tool_name} returned ({len(result_str)} chars)")
                    all_tool_results.append({
                        "tool": tool_name,
                        "args": tool_args,
                        "result": result
                    })
                    conversation.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result_str
                    })
                except Exception as e:
                    print(f"[{self.name}] Tool {tool_name} FAILED: {e}")
                    conversation.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps({"error": str(e)})
                    })

        # Max iterations reached — get final response without tools
        print(f"[{self.name}] Max iterations reached, getting final response without tools")
        final_kwargs = {"model": self.model, "messages": conversation}
        if self.tools:
            final_kwargs["tools"] = self.tools
        if self.response_format:
            final_kwargs["response_format"] = self.response_format
        response = litellm.completion(**final_kwargs)
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
