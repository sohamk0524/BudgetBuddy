"""
Reasoning Engine for BudgetBuddy.
Implements the ReAct (Reasoning + Acting) pattern for intelligent agent decision-making.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from models import AssistantResponse, VisualPayload, SankeyNode
from tools import ToolContext, ToolRegistry, ToolResult, get_default_registry
from services.conversation_manager import (
    ConversationManager,
    ConversationContext,
    get_conversation_manager,
)
from services.llm_service import BudgetBuddyAgent, OllamaConnectionError, OllamaError

logger = logging.getLogger(__name__)


@dataclass
class ReasoningStep:
    """A single step in the reasoning process."""
    step_type: str  # "thought", "action", "observation", "response"
    content: str
    tool_name: Optional[str] = None
    tool_args: Optional[Dict[str, Any]] = None
    tool_result: Optional[Dict[str, Any]] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class AgentResponse:
    """Response from the reasoning engine."""
    text: str
    visual: Optional[Dict[str, Any]] = None
    reasoning_trace: List[ReasoningStep] = field(default_factory=list)
    tool_results: List[Dict[str, Any]] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    ui_events: List[Dict[str, Any]] = field(default_factory=list)

    def to_assistant_response(self) -> AssistantResponse:
        """Convert to AssistantResponse for API compatibility."""
        return AssistantResponse(
            text_message=self.text,
            visual_payload=self.visual
        )


class ReasoningEngine:
    """
    Implements ReAct (Reasoning + Acting) pattern for agent decision-making.

    The engine processes user input through a loop:
    1. Thought: Analyze what the user wants
    2. Action: Select and execute appropriate tool (if needed)
    3. Observation: Process tool results
    4. Repeat until ready to respond
    """

    def __init__(
        self,
        llm_agent: Optional[BudgetBuddyAgent] = None,
        tool_registry: Optional[ToolRegistry] = None,
        conversation_manager: Optional[ConversationManager] = None,
        max_iterations: int = 5
    ):
        """
        Initialize the reasoning engine.

        Args:
            llm_agent: LLM agent for generating responses
            tool_registry: Registry of available tools
            conversation_manager: Manager for conversation state
            max_iterations: Maximum reasoning iterations before forcing response
        """
        self._llm = llm_agent or BudgetBuddyAgent()
        self._tools = tool_registry or get_default_registry()
        self._conversations = conversation_manager or get_conversation_manager()
        self._max_iterations = max_iterations

    async def process(
        self,
        user_input: str,
        user_id: int,
        session_id: Optional[str] = None,
        system_prompt: Optional[str] = None,
        user_profile: Optional[Dict[str, Any]] = None,
        financial_summary: Optional[Dict[str, Any]] = None
    ) -> AgentResponse:
        """
        Process user input through the reasoning loop.

        Args:
            user_input: The user's message
            user_id: User ID for context
            session_id: Optional session ID for conversation continuity
            system_prompt: Optional custom system prompt
            user_profile: Optional user profile for context
            financial_summary: Optional financial summary for context

        Returns:
            AgentResponse with text, visual, and reasoning trace
        """
        reasoning_trace: List[ReasoningStep] = []
        tool_results: List[Dict[str, Any]] = []

        # Get or create conversation context
        if session_id:
            conv_context = self._conversations.get_or_create_context(session_id, user_id)
            # Resolve references in user input
            resolved_input = self._conversations.resolve_references(session_id, user_input)
            # Add user message
            self._conversations.add_user_message(session_id, user_input)
        else:
            conv_context = None
            resolved_input = user_input

        # Build system prompt with context
        if system_prompt is None:
            system_prompt = self._conversations.build_system_prompt(
                user_profile=user_profile,
                financial_summary=financial_summary,
                user_id=user_id
            )

        # Build tool context
        tool_context = self._build_tool_context(user_id, user_profile, session_id)

        # Get available tools based on context
        available_tools = self._tools.get_openai_schemas(tool_context)

        # Determine if we should offer tools
        should_use_tools = self._should_use_tools(resolved_input)

        # Build conversation messages
        messages = [{"role": "system", "content": system_prompt}]

        # Add conversation history if available
        if conv_context:
            history = conv_context.get_llm_messages(max_turns=6)
            messages.extend(history)

        # Add current user message
        messages.append({"role": "user", "content": resolved_input})

        # Check LLM availability
        if not self._llm.is_available():
            return self._fallback_response(resolved_input)

        try:
            # Reasoning loop
            for iteration in range(self._max_iterations):
                reasoning_trace.append(ReasoningStep(
                    step_type="thought",
                    content=f"Iteration {iteration + 1}: Processing user request"
                ))

                # Call LLM with or without tools
                if should_use_tools and available_tools:
                    response = self._llm.chat(messages, tools=available_tools)
                else:
                    response = self._llm.chat(messages, tools=None)

                message = response.choices[0].message

                # Check if model wants to use tools
                if not message.tool_calls:
                    # No tool calls - model is ready to respond
                    response_text = message.content or ""

                    reasoning_trace.append(ReasoningStep(
                        step_type="response",
                        content=response_text
                    ))

                    # Build visual from tool results
                    visual = self._determine_visual(tool_results)

                    # Get suggestions from tool results
                    suggestions = self._extract_suggestions(tool_results)

                    # Add assistant message to conversation
                    if session_id:
                        self._conversations.add_assistant_message(
                            session_id,
                            response_text,
                            {"has_visual": visual is not None}
                        )

                    return AgentResponse(
                        text=response_text,
                        visual=visual,
                        reasoning_trace=reasoning_trace,
                        tool_results=tool_results,
                        suggestions=suggestions
                    )

                # Model wants to use tools
                reasoning_trace.append(ReasoningStep(
                    step_type="action",
                    content=f"Calling {len(message.tool_calls)} tool(s)"
                ))

                # Add assistant message with tool calls to conversation
                messages.append({
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

                    reasoning_trace.append(ReasoningStep(
                        step_type="action",
                        content=f"Executing tool: {tool_name}",
                        tool_name=tool_name,
                        tool_args=tool_args
                    ))

                    # Execute the tool
                    result = await self._tools.execute(tool_name, tool_args, tool_context)

                    tool_results.append({
                        "tool": tool_name,
                        "args": tool_args,
                        "result": result.data if result.success else {"error": result.error},
                        "success": result.success,
                        "visual": result.visual,
                        "suggestions": result.follow_up_suggestions
                    })

                    reasoning_trace.append(ReasoningStep(
                        step_type="observation",
                        content=f"Tool {tool_name} returned: {result.message}",
                        tool_name=tool_name,
                        tool_result=result.data if result.success else {"error": result.error}
                    ))

                    # Add tool result to messages
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(result.data) if result.success else json.dumps({"error": result.error})
                    })

                    # Record tool call in conversation
                    if session_id:
                        self._conversations.add_tool_call(
                            session_id,
                            tool_name,
                            tool_args,
                            result.data if result.success else {"error": result.error},
                            tool_call.id
                        )

            # Max iterations reached - get final response without tools
            response = self._llm.chat(messages, tools=None)
            response_text = response.choices[0].message.content or "I wasn't able to complete that request."

            visual = self._determine_visual(tool_results)
            suggestions = self._extract_suggestions(tool_results)

            if session_id:
                self._conversations.add_assistant_message(session_id, response_text)

            return AgentResponse(
                text=response_text,
                visual=visual,
                reasoning_trace=reasoning_trace,
                tool_results=tool_results,
                suggestions=suggestions
            )

        except OllamaConnectionError:
            return self._fallback_response(resolved_input, "I can't connect to my AI backend. Please make sure Ollama is running.")
        except OllamaError as e:
            logger.error(f"Ollama error: {e}")
            return self._fallback_response(resolved_input, "I encountered an error. Please try again.")
        except Exception as e:
            logger.exception(f"Reasoning engine error: {e}")
            return self._fallback_response(resolved_input)

    def process_sync(
        self,
        user_input: str,
        user_id: int,
        session_id: Optional[str] = None,
        system_prompt: Optional[str] = None,
        user_profile: Optional[Dict[str, Any]] = None,
        financial_summary: Optional[Dict[str, Any]] = None
    ) -> AgentResponse:
        """
        Synchronous wrapper for process().
        """
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(
                        asyncio.run,
                        self.process(user_input, user_id, session_id, system_prompt, user_profile, financial_summary)
                    )
                    return future.result()
            else:
                return loop.run_until_complete(
                    self.process(user_input, user_id, session_id, system_prompt, user_profile, financial_summary)
                )
        except RuntimeError:
            return asyncio.run(
                self.process(user_input, user_id, session_id, system_prompt, user_profile, financial_summary)
            )

    def _build_tool_context(
        self,
        user_id: int,
        user_profile: Optional[Dict[str, Any]],
        session_id: Optional[str]
    ) -> ToolContext:
        """Build tool context from user information."""
        # Check if user has a budget plan
        has_plan = False
        has_statement = False
        try:
            from db_models import BudgetPlan, SavedStatement
            plan = BudgetPlan.query.filter_by(user_id=user_id).first()
            has_plan = plan is not None
            statement = SavedStatement.query.filter_by(user_id=user_id).first()
            has_statement = statement is not None
        except Exception as e:
            logger.debug(f"Could not check user plan/statement status: {e}")

        return ToolContext(
            user_id=user_id,
            session_id=session_id,
            is_authenticated=True,
            has_profile=user_profile is not None,
            has_plan=has_plan,
            has_statement=has_statement,
        )

    def _should_use_tools(self, text: str) -> bool:
        """
        Determine if the message is likely asking about financial data.
        Only provide tools for finance-related queries.
        """
        text_lower = text.lower()

        # Keywords that suggest user wants financial data
        finance_keywords = [
            "budget", "spend", "spending", "expense", "expenses", "money",
            "afford", "cost", "balance", "account", "savings", "save",
            "income", "salary", "pay", "payment", "bill", "bills",
            "overview", "breakdown", "status", "track", "tracking",
            "how much", "how am i", "can i buy", "should i buy",
            "financial", "finances", "cash", "funds", "dollars", "$"
        ]

        return any(keyword in text_lower for keyword in finance_keywords)

    def _determine_visual(self, tool_results: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Determine the appropriate visual payload from tool results."""
        for result in tool_results:
            if result.get("visual"):
                return result["visual"]

            tool_name = result.get("tool", "")
            data = result.get("result", {})

            if tool_name == "get_budget_overview" and result.get("success", True):
                nodes = data.get("nodes", [])
                if nodes:
                    return VisualPayload.sankey_flow([
                        SankeyNode(id=n["id"], name=n["name"], value=n["value"])
                        for n in nodes
                    ])

            elif tool_name == "get_spending_status" and result.get("success", True):
                return VisualPayload.burndown_chart(
                    spent=data.get("spent", 0),
                    budget=data.get("budget", 0),
                    ideal_pace=data.get("idealPace", 0)
                )

        return None

    def _extract_suggestions(self, tool_results: List[Dict[str, Any]]) -> List[str]:
        """Extract follow-up suggestions from tool results."""
        suggestions = []
        for result in tool_results:
            result_suggestions = result.get("suggestions", [])
            suggestions.extend(result_suggestions)
        # Deduplicate while preserving order
        seen = set()
        unique = []
        for s in suggestions:
            if s not in seen:
                seen.add(s)
                unique.append(s)
        return unique[:3]  # Return top 3

    def _fallback_response(
        self,
        user_input: str,
        error_message: Optional[str] = None
    ) -> AgentResponse:
        """Provide a fallback response when AI is unavailable."""
        from services.data_mock import get_budget_overview_data, get_spending_status_data

        if error_message:
            return AgentResponse(text=error_message)

        text_lower = user_input.lower()

        # Greeting fallback
        if any(word in text_lower for word in ["hi", "hello", "hey"]):
            return AgentResponse(
                text="Hey there! I'm BudgetBuddy. I'm having some technical difficulties, but I'm here to help with your finances!"
            )

        # Budget overview fallback
        if any(keyword in text_lower for keyword in ["budget", "overview", "breakdown"]):
            data = get_budget_overview_data()
            nodes = [SankeyNode(**node) for node in data["nodes"]]
            return AgentResponse(
                text="Here's your budget overview. (Note: AI is temporarily unavailable)",
                visual=VisualPayload.sankey_flow(nodes)
            )

        # Spending status fallback
        if any(keyword in text_lower for keyword in ["afford", "status", "overspending", "track"]):
            data = get_spending_status_data()
            return AgentResponse(
                text=f"You've spent ${data['spent']:,.2f} of your ${data['budget']:,.2f} budget. (AI temporarily unavailable)",
                visual=VisualPayload.burndown_chart(
                    spent=data["spent"],
                    budget=data["budget"],
                    ideal_pace=data["idealPace"]
                )
            )

        # Default fallback
        return AgentResponse(
            text="I'm having some technical difficulties. Try asking about your budget or spending status!"
        )


# Singleton instance
_reasoning_engine: Optional[ReasoningEngine] = None


def get_reasoning_engine() -> ReasoningEngine:
    """Get the singleton reasoning engine instance."""
    global _reasoning_engine
    if _reasoning_engine is None:
        _reasoning_engine = ReasoningEngine()
    return _reasoning_engine
