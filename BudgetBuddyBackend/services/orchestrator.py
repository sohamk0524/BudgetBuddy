"""
Orchestrator service - The "Brain" of BudgetBuddy.
Integrates the ReasoningEngine, ToolRegistry, ConversationManager, and ProfileHealthEngine.
"""

import re
import logging
from typing import Optional, Dict, Any

from models import AssistantResponse, VisualPayload, SankeyNode
from services.llm_service import BudgetBuddyAgent, OllamaConnectionError, OllamaError
from services.data_mock import get_budget_overview_data, get_spending_status_data

# New architecture imports
from services.reasoning_engine import ReasoningEngine, get_reasoning_engine
from services.conversation_manager import ConversationManager, get_conversation_manager
from services.state_engine import ProfileHealthEngine, get_health_engine

logger = logging.getLogger(__name__)


# =============================================================================
# USER PROFILE UTILITIES
# =============================================================================

def get_user_profile(user_id) -> Optional[Dict[str, Any]]:
    """
    Fetch user's financial profile from the database.
    Returns None if user or profile doesn't exist.
    """
    try:
        from db_models import User
        user = User.query.get(user_id)
        if user and user.profile:
            return {
                "monthly_income": user.profile.monthly_income or 0,
                "fixed_expenses": user.profile.fixed_expenses or 0,
                "discretionary": (user.profile.monthly_income or 0) - (user.profile.fixed_expenses or 0),
                "savings_goal_name": user.profile.savings_goal_name,
                "savings_goal_target": user.profile.savings_goal_target or 0,
                "financial_personality": user.profile.financial_personality,
                "primary_goal": user.profile.primary_goal,
                "name": user.email.split("@")[0] if user.email else "User"
            }
    except Exception as e:
        logger.debug(f"Could not fetch profile for user {user_id}: {e}")
    return None


def get_financial_summary(user_id) -> Optional[Dict[str, Any]]:
    """
    Get current financial summary for a user.
    Uses mock data for now, can be enhanced with real data.
    """
    try:
        from services.data_mock import get_spending_status_data, get_account_balance_data
        spending = get_spending_status_data()
        balance = get_account_balance_data()

        return {
            "safe_to_spend": balance.get("checking_balance", 0),
            "spent_this_month": spending.get("spent", 0),
            "budget_remaining": spending.get("budget", 0) - spending.get("spent", 0),
            "days_remaining": spending.get("daysRemaining", 0)
        }
    except Exception as e:
        logger.debug(f"Could not fetch financial summary: {e}")
    return None


def check_user_has_plan(user_id) -> bool:
    """Check if user has a budget plan."""
    try:
        from db_models import BudgetPlan
        plan = BudgetPlan.query.filter_by(user_id=user_id).first()
        return plan is not None
    except Exception:
        return False


def check_user_has_statement(user_id) -> bool:
    """Check if user has an uploaded statement."""
    try:
        from db_models import SavedStatement
        statement = SavedStatement.query.filter_by(user_id=user_id).first()
        return statement is not None
    except Exception:
        return False


# =============================================================================
# AGENT ORCHESTRATOR CLASS
# =============================================================================

class AgentOrchestrator:
    """
    Main orchestrator that coordinates all agent components.
    Provides the primary interface for processing user messages.
    """

    def __init__(
        self,
        reasoning_engine: Optional[ReasoningEngine] = None,
        conversation_manager: Optional[ConversationManager] = None,
        health_engine: Optional[ProfileHealthEngine] = None
    ):
        """
        Initialize the orchestrator with all components.

        Args:
            reasoning_engine: Engine for processing messages
            conversation_manager: Manager for conversation state
            health_engine: Engine for proactive health monitoring
        """
        self._reasoning = reasoning_engine or get_reasoning_engine()
        self._conversations = conversation_manager or get_conversation_manager()
        self._health = health_engine or get_health_engine()

    def process_message(
        self,
        text: str,
        user_id: int,
        session_id: Optional[str] = None,
        is_session_start: bool = False
    ) -> AssistantResponse:
        """
        Process a user message through the full agent pipeline.

        Args:
            text: User's message
            user_id: User ID
            session_id: Optional session ID for conversation continuity
            is_session_start: Whether this is the start of a new session

        Returns:
            AssistantResponse with text and optional visual payload
        """
        # Get user context
        user_profile = get_user_profile(user_id)
        financial_summary = get_financial_summary(user_id)

        # Check for proactive interventions on session start
        if is_session_start:
            health_context = self._health.get_greeting_context(user_id)
            if health_context.greeting_override:
                # Return proactive message instead of processing user message
                return AssistantResponse(
                    text_message=health_context.greeting_override,
                    visual_payload=None
                )

        # Process through reasoning engine
        try:
            response = self._reasoning.process_sync(
                user_input=text,
                user_id=user_id,
                session_id=session_id,
                user_profile=user_profile,
                financial_summary=financial_summary
            )

            return response.to_assistant_response()

        except Exception as e:
            logger.exception(f"Error processing message: {e}")
            return _fallback_response(text)

    def get_proactive_message(self, user_id: int) -> Optional[str]:
        """
        Check if there's a proactive message for the user.

        Args:
            user_id: User ID

        Returns:
            Proactive message or None
        """
        return self._health.get_proactive_message(user_id)

    def start_session(self, user_id: int, session_id: Optional[str] = None) -> str:
        """
        Start a new conversation session.

        Args:
            user_id: User ID
            session_id: Optional specific session ID

        Returns:
            Session ID
        """
        context = self._conversations.create_session(user_id, session_id)
        return context.session_id

    def end_session(self, session_id: str) -> bool:
        """
        End a conversation session.

        Args:
            session_id: Session ID to end

        Returns:
            True if session was found and ended
        """
        return self._conversations.end_session(session_id)


# =============================================================================
# SINGLETON AND BACKWARD COMPATIBILITY
# =============================================================================

# Singleton orchestrator instance
_orchestrator: Optional[AgentOrchestrator] = None


def get_orchestrator() -> AgentOrchestrator:
    """Get the singleton orchestrator instance."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = AgentOrchestrator()
    return _orchestrator


# Legacy agent for backward compatibility
agent = BudgetBuddyAgent(model="llama3.2:3b")


def _should_use_tools(text: str) -> bool:
    """
    Determine if the message is likely asking about financial data.
    Only provide tools for finance-related queries to prevent over-eager tool calling.
    """
    text_lower = text.lower()

    finance_keywords = [
        "budget", "spend", "spending", "expense", "expenses", "money",
        "afford", "cost", "balance", "account", "savings", "save",
        "income", "salary", "pay", "payment", "bill", "bills",
        "overview", "breakdown", "status", "track", "tracking",
        "how much", "how am i", "can i buy", "should i buy",
        "financial", "finances", "cash", "funds", "dollars", "$"
    ]

    return any(keyword in text_lower for keyword in finance_keywords)


def _extract_amount(text: str) -> float:
    """Extract a dollar amount from text, default to 100 if not found."""
    match = re.search(r'\$?([\d,]+(?:\.\d{2})?)', text)
    if match:
        return float(match.group(1).replace(',', ''))
    return 100.0


def _handle_personalized_query(text: str, user_id) -> Optional[AssistantResponse]:
    """
    Handle queries that require user's financial profile.
    Returns None if no personalized response is needed.
    """
    text_lower = text.lower()
    profile = get_user_profile(user_id)

    if not profile:
        return None

    discretionary = profile["discretionary"]

    # Handle "afford" or "can I buy" queries
    if "afford" in text_lower or "can i buy" in text_lower:
        amount = _extract_amount(text)

        if amount <= discretionary:
            response_text = f"Based on your budget, you have ${discretionary:,.2f} discretionary income. You can afford this ${amount:,.2f} purchase!"
        else:
            response_text = f"Your discretionary budget is ${discretionary:,.2f}. A ${amount:,.2f} purchase would exceed your available funds."

        return AssistantResponse(
            text_message=response_text,
            visual_payload=VisualPayload.burndown_chart(
                spent=amount,
                budget=discretionary,
                ideal_pace=discretionary * 0.5
            )
        )

    # Handle "plan" queries
    if "plan" in text_lower:
        income = profile["monthly_income"]
        expenses = profile["fixed_expenses"]

        nodes = [
            SankeyNode(id="income", name="Income", value=income),
            SankeyNode(id="expenses", name="Fixed Expenses", value=expenses),
            SankeyNode(id="discretionary", name="Discretionary", value=discretionary),
        ]

        if profile["savings_goal_name"]:
            nodes.append(SankeyNode(
                id="savings",
                name=profile["savings_goal_name"],
                value=profile["savings_goal_target"]
            ))

        return AssistantResponse(
            text_message=f"Here's your financial plan. You earn ${income:,.2f}/month with ${expenses:,.2f} in fixed expenses, leaving ${discretionary:,.2f} for spending and savings.",
            visual_payload=VisualPayload.sankey_flow(nodes)
        )

    return None


def _fallback_response(text: str, error_message: str = None) -> AssistantResponse:
    """
    Provide a fallback response when the AI is unavailable.
    """
    if error_message:
        return AssistantResponse(
            text_message=error_message,
            visual_payload=None
        )

    text_lower = text.lower()

    if any(word in text_lower for word in ["hi", "hello", "hey"]):
        return AssistantResponse(
            text_message="Hey there! I'm BudgetBuddy. I'm having some technical difficulties, but I'm here to help with your finances!",
            visual_payload=None
        )

    if any(keyword in text_lower for keyword in ["budget", "overview", "spending breakdown"]):
        data = get_budget_overview_data()
        nodes = [SankeyNode(**node) for node in data["nodes"]]
        return AssistantResponse(
            text_message="Here's your budget overview. (Note: AI is temporarily unavailable)",
            visual_payload=VisualPayload.sankey_flow(nodes)
        )

    if any(keyword in text_lower for keyword in ["afford", "status", "overspending"]):
        data = get_spending_status_data()
        return AssistantResponse(
            text_message=f"You've spent ${data['spent']:,.2f} of your ${data['budget']:,.2f} budget. (AI temporarily unavailable)",
            visual_payload=VisualPayload.burndown_chart(
                spent=data["spent"],
                budget=data["budget"],
                ideal_pace=data["idealPace"]
            )
        )

    return AssistantResponse(
        text_message="I'm having some technical difficulties. Try asking about your budget or spending status!",
        visual_payload=None
    )


# =============================================================================
# MAIN ENTRY POINT (BACKWARD COMPATIBLE)
# =============================================================================

def process_message(text: str, user_id: str = "default") -> AssistantResponse:
    """
    Process user message using the AI agent with optional tool calling.

    This function maintains backward compatibility with the existing API
    while using the new architecture under the hood.

    Args:
        text: The user's input message
        user_id: Optional user identifier for context

    Returns:
        AssistantResponse with text and optional visual payload
    """
    # Convert user_id to int if possible
    try:
        uid = int(user_id)
    except (ValueError, TypeError):
        uid = 0

    # Try personalized response first (backward compatibility)
    personalized = _handle_personalized_query(text, uid)
    if personalized:
        return personalized

    # Use new orchestrator
    try:
        orchestrator = get_orchestrator()
        return orchestrator.process_message(
            text=text,
            user_id=uid,
            session_id=None,  # No session for backward compatibility
            is_session_start=False
        )
    except Exception as e:
        logger.error(f"Orchestrator failed, falling back: {e}")
        # Fall back to legacy processing if new system fails
        return _legacy_process_message(text, user_id)


def _legacy_process_message(text: str, user_id: str) -> AssistantResponse:
    """
    Legacy message processing for fallback.
    Uses the old tool execution system.
    """
    from services.tools import get_tool_definitions, execute_tool

    try:
        if not agent.is_available():
            return _fallback_response(
                text,
                "I'm having trouble connecting to my AI backend. Please make sure Ollama is running with 'ollama serve'."
            )

        # System prompt
        # Convert user_id to int if possible
        try:
            uid = int(user_id)
        except (ValueError, TypeError):
            uid = 0

        system_prompt = f"""You are BudgetBuddy, a friendly AI financial assistant. You help users understand their finances, track spending, and make smart money decisions.

CURRENT USER: The user's ID is {uid}. Use this ID when calling tools that require user_id.

## CONVERSATION GUIDELINES
- Be warm, helpful, and conversational
- Keep responses concise but informative (2-4 sentences for simple questions, more for analysis)
- For greetings like "hi", "hello", "hey" - just respond naturally and friendly, do NOT use any tools
- For general questions like "what can you do?" - explain your capabilities without using tools

## CRITICAL WORKFLOW FOR FINANCIAL QUESTIONS
When a user asks about their budget, spending, or finances, follow this workflow:

1. FIRST call check_user_setup_status with user_id={uid}
2. If is_fully_setup is false:
   - Guide them to complete setup first
   - DO NOT call budget/spending tools
3. If is_fully_setup is true:
   - Call the appropriate tool(s) to fetch their data
   - ANALYZE the data and provide intelligent insights (see Analysis Guidelines below)

## WHEN TO USE TOOLS
- check_user_setup_status: Call FIRST for any financial question (user_id={uid})
- suggest_next_action: When user needs onboarding guidance (user_id={uid})
- get_budget_overview: For budget breakdown, where money goes, spending categories
- get_spending_status: For spending pace, affordability, "am I overspending", budget tracking
- get_account_balance: For balance inquiries, available funds
- get_savings_progress: For savings goals progress

## ANALYSIS GUIDELINES - THIS IS CRITICAL
When you receive tool results, you MUST analyze the data and provide actionable insights:

**For "help me reduce spending" or saving advice:**
1. Call get_spending_status to get categoryBreakdown
2. Look at the categoryBreakdown to identify high-spending areas
3. Compare spending to budget allocations
4. Provide SPECIFIC recommendations like:
   - "Your Dining Out spending ($X) is high. Consider meal prepping to save $50-100/month"
   - "Shopping ($X) could be reduced by waiting 48 hours before purchases"

**For "can I afford X" questions:**
1. Call get_spending_status
2. Check dailyBudgetRemaining and daysRemaining
3. Calculate if the purchase fits within remaining budget
4. Give a clear yes/no with reasoning

**For "how am I doing" questions:**
1. Call get_spending_status
2. Look at status (under_budget, on_track, over_budget)
3. Explain their pace using specific numbers

## DO NOT USE TOOLS FOR
- Greetings (hi, hello, hey)
- General questions (how are you, what can you do)
- Non-financial topics

## RESPONSE STYLE
- Be encouraging but honest about their financial situation
- ALWAYS use specific numbers from tool results
- Provide actionable, specific advice - not generic tips
- If recommending changes, estimate potential savings"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text}
        ]

        use_tools = _should_use_tools(text)
        tools = get_tool_definitions() if use_tools else None

        if use_tools:
            result = agent.chat_with_tools(
                messages=messages,
                tools=tools,
                tool_executor=execute_tool,
                max_iterations=3
            )
        else:
            response = agent.chat(messages, tools=None)
            result = {
                "content": response.choices[0].message.content or "",
                "tool_results": []
            }

        response_text = result.get("content", "I'm not sure how to help with that. Try asking about your budget or spending!")
        tool_results = result.get("tool_results", [])

        visual_payload = _determine_visual_payload(tool_results)

        return AssistantResponse(
            text_message=response_text,
            visual_payload=visual_payload
        )

    except OllamaConnectionError:
        return _fallback_response(
            text,
            "I can't connect to my AI backend right now. Please make sure Ollama is running."
        )
    except OllamaError:
        return _fallback_response(
            text,
            "I encountered an error processing your request. Please try again."
        )
    except Exception as e:
        logger.error(f"Legacy orchestrator error: {e}")
        return _fallback_response(text)


def _determine_visual_payload(tool_results: list) -> Optional[Dict[str, Any]]:
    """
    Determine the appropriate visual payload based on which tools were called.
    Returns None if no tools were called (for regular conversation).
    """
    if not tool_results:
        return None

    for tool_result in tool_results:
        tool_name = tool_result.get("tool", "")
        result_data = tool_result.get("result", {})

        if tool_name == "get_budget_overview":
            nodes = result_data.get("nodes", [])
            return VisualPayload.sankey_flow([
                SankeyNode(
                    id=node["id"],
                    name=node["name"],
                    value=node["value"]
                )
                for node in nodes
            ])

        elif tool_name == "get_spending_status":
            return VisualPayload.burndown_chart(
                spent=result_data.get("spent", 0),
                budget=result_data.get("budget", 0),
                ideal_pace=result_data.get("idealPace", 0)
            )

    return None


# =============================================================================
# NEW API ENDPOINTS SUPPORT
# =============================================================================

def process_message_with_session(
    text: str,
    user_id: int,
    session_id: str,
    is_session_start: bool = False
) -> Dict[str, Any]:
    """
    Process message with full session support.
    Returns extended response with session info and suggestions.

    Args:
        text: User's message
        user_id: User ID
        session_id: Session ID
        is_session_start: Whether this is session start

    Returns:
        Dict with text, visual, session_id, suggestions, and ui_events
    """
    orchestrator = get_orchestrator()

    # Ensure session exists
    if is_session_start:
        orchestrator.start_session(user_id, session_id)

    response = orchestrator.process_message(
        text=text,
        user_id=user_id,
        session_id=session_id,
        is_session_start=is_session_start
    )

    return {
        "textMessage": response.text_message,
        "visualPayload": response.visual_payload,
        "sessionId": session_id,
        "suggestions": [],  # TODO: Extract from reasoning engine
        "uiEvents": []  # TODO: Extract from reasoning engine
    }


def check_proactive_message(user_id: int) -> Optional[Dict[str, Any]]:
    """
    Check for proactive messages for a user.

    Args:
        user_id: User ID

    Returns:
        Dict with message and suggested action, or None
    """
    health_engine = get_health_engine()
    context = health_engine.get_greeting_context(user_id)

    if context.greeting_override:
        return {
            "message": context.greeting_override,
            "suggestedAction": context.suggested_actions[0] if context.suggested_actions else None,
            "severity": context.priority_condition.condition.severity.value if context.priority_condition else "info"
        }

    return None
