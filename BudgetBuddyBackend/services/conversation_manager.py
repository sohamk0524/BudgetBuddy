"""
Conversation Manager for BudgetBuddy.
Handles session memory, context building, and reference resolution.
"""

import re
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
import logging
import json

logger = logging.getLogger(__name__)


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class ConversationTurn:
    """A single turn in the conversation."""
    role: Literal["user", "assistant", "system", "tool"]
    content: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    # For tool calls
    tool_name: Optional[str] = None
    tool_args: Optional[Dict[str, Any]] = None
    tool_result: Optional[Dict[str, Any]] = None
    tool_call_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
        }
        if self.tool_name:
            result["tool_name"] = self.tool_name
        if self.tool_args:
            result["tool_args"] = self.tool_args
        if self.tool_result:
            result["tool_result"] = self.tool_result
        if self.tool_call_id:
            result["tool_call_id"] = self.tool_call_id
        return result

    def to_llm_message(self) -> Dict[str, Any]:
        """Convert to LLM message format."""
        if self.role == "tool":
            return {
                "role": "tool",
                "tool_call_id": self.tool_call_id or "",
                "content": self.content
            }
        return {
            "role": self.role,
            "content": self.content
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ConversationTurn':
        """Create from dictionary."""
        timestamp = data.get("timestamp")
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
        elif timestamp is None:
            timestamp = datetime.utcnow()

        return cls(
            role=data["role"],
            content=data["content"],
            timestamp=timestamp,
            metadata=data.get("metadata", {}),
            tool_name=data.get("tool_name"),
            tool_args=data.get("tool_args"),
            tool_result=data.get("tool_result"),
            tool_call_id=data.get("tool_call_id"),
        )


@dataclass
class MentionedEntity:
    """An entity mentioned in conversation for reference tracking."""
    entity_type: str  # "subscription", "category", "goal", "amount", "merchant"
    value: Any
    mentioned_at: datetime = field(default_factory=datetime.utcnow)
    turn_index: int = 0


@dataclass
class ConversationContext:
    """
    Full context for a conversation session.
    Tracks history, mentioned entities, and conversation state.
    """
    session_id: str
    user_id: int
    turns: List[ConversationTurn] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_activity: datetime = field(default_factory=datetime.utcnow)

    # Extracted entities for reference resolution
    mentioned_subscriptions: List[str] = field(default_factory=list)
    mentioned_categories: List[str] = field(default_factory=list)
    mentioned_goals: List[str] = field(default_factory=list)
    mentioned_amounts: List[float] = field(default_factory=list)
    mentioned_merchants: List[str] = field(default_factory=list)

    # Current conversation focus
    active_topic: Optional[str] = None

    # Pending actions awaiting confirmation
    pending_confirmation: Optional[Dict[str, Any]] = None

    def add_turn(self, turn: ConversationTurn) -> None:
        """Add a turn to the conversation."""
        self.turns.append(turn)
        self.last_activity = datetime.utcnow()

    def get_recent_turns(self, max_turns: int = 10) -> List[ConversationTurn]:
        """Get the most recent turns."""
        return self.turns[-max_turns:]

    def get_llm_messages(self, max_turns: int = 10) -> List[Dict[str, Any]]:
        """Get recent turns formatted for LLM context."""
        return [
            turn.to_llm_message()
            for turn in self.get_recent_turns(max_turns)
            if turn.role in ("user", "assistant", "tool")
        ]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "turns": [turn.to_dict() for turn in self.turns],
            "created_at": self.created_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "mentioned_subscriptions": self.mentioned_subscriptions,
            "mentioned_categories": self.mentioned_categories,
            "mentioned_goals": self.mentioned_goals,
            "mentioned_amounts": self.mentioned_amounts,
            "mentioned_merchants": self.mentioned_merchants,
            "active_topic": self.active_topic,
            "pending_confirmation": self.pending_confirmation,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ConversationContext':
        """Create from dictionary."""
        return cls(
            session_id=data["session_id"],
            user_id=data["user_id"],
            turns=[ConversationTurn.from_dict(t) for t in data.get("turns", [])],
            created_at=datetime.fromisoformat(data.get("created_at", datetime.utcnow().isoformat())),
            last_activity=datetime.fromisoformat(data.get("last_activity", datetime.utcnow().isoformat())),
            mentioned_subscriptions=data.get("mentioned_subscriptions", []),
            mentioned_categories=data.get("mentioned_categories", []),
            mentioned_goals=data.get("mentioned_goals", []),
            mentioned_amounts=data.get("mentioned_amounts", []),
            mentioned_merchants=data.get("mentioned_merchants", []),
            active_topic=data.get("active_topic"),
            pending_confirmation=data.get("pending_confirmation"),
        )


# =============================================================================
# ENTITY EXTRACTOR
# =============================================================================

class EntityExtractor:
    """Extracts entities from user messages for reference tracking."""

    # Common spending categories
    CATEGORIES = [
        "rent", "housing", "groceries", "food", "dining", "restaurants",
        "transportation", "gas", "utilities", "entertainment", "shopping",
        "subscriptions", "healthcare", "insurance", "education", "travel",
        "personal care", "clothing", "gifts", "savings"
    ]

    # Common subscription services
    SUBSCRIPTIONS = [
        "netflix", "spotify", "hulu", "disney+", "disney plus", "hbo", "hbo max",
        "amazon prime", "prime", "apple music", "youtube premium", "youtube",
        "gym", "fitness", "adobe", "microsoft", "office 365", "dropbox",
        "icloud", "google one", "chatgpt", "openai"
    ]

    # Amount patterns
    AMOUNT_PATTERN = re.compile(r'\$?([\d,]+(?:\.\d{2})?)')

    def extract(self, text: str) -> Dict[str, List[Any]]:
        """
        Extract all entities from text.

        Returns:
            Dict with keys: subscriptions, categories, amounts, merchants
        """
        text_lower = text.lower()

        return {
            "subscriptions": self._extract_subscriptions(text_lower),
            "categories": self._extract_categories(text_lower),
            "amounts": self._extract_amounts(text),
            "goals": self._extract_goals(text_lower),
        }

    def _extract_subscriptions(self, text: str) -> List[str]:
        """Extract mentioned subscription services."""
        found = []
        for sub in self.SUBSCRIPTIONS:
            if sub in text:
                # Normalize the name
                normalized = sub.replace("+", " plus").title()
                if normalized not in found:
                    found.append(normalized)
        return found

    def _extract_categories(self, text: str) -> List[str]:
        """Extract mentioned spending categories."""
        found = []
        for category in self.CATEGORIES:
            if category in text:
                if category not in found:
                    found.append(category)
        return found

    def _extract_amounts(self, text: str) -> List[float]:
        """Extract dollar amounts from text."""
        amounts = []
        matches = self.AMOUNT_PATTERN.findall(text)
        for match in matches:
            try:
                amount = float(match.replace(",", ""))
                if amount > 0:
                    amounts.append(amount)
            except ValueError:
                continue
        return amounts

    def _extract_goals(self, text: str) -> List[str]:
        """Extract mentioned savings goals."""
        goals = []
        goal_patterns = [
            r"(?:emergency\s+fund|rainy\s+day)",
            r"(?:vacation|trip|travel)",
            r"(?:down\s+payment|house|home)",
            r"(?:car|vehicle)",
            r"(?:retirement)",
            r"(?:wedding)",
            r"(?:laptop|computer|phone)",
        ]
        for pattern in goal_patterns:
            if re.search(pattern, text):
                match = re.search(pattern, text)
                if match:
                    goals.append(match.group(0))
        return goals


# =============================================================================
# REFERENCE RESOLVER
# =============================================================================

class ReferenceResolver:
    """Resolves anaphoric references in user messages."""

    def resolve(self, message: str, context: ConversationContext) -> str:
        """
        Resolve references in a message to their full form.

        Examples:
            "Cancel that subscription" -> "Cancel Netflix subscription"
            "How much on it?" -> "How much on dining?"
        """
        resolved = message

        # Subscription references
        if context.mentioned_subscriptions:
            patterns = [
                (r'\bthat subscription\b', context.mentioned_subscriptions[-1]),
                (r'\bthe subscription\b', context.mentioned_subscriptions[-1]),
                (r'\bthis subscription\b', context.mentioned_subscriptions[-1]),
            ]
            for pattern, replacement in patterns:
                resolved = re.sub(pattern, replacement, resolved, flags=re.IGNORECASE)

        # Category references
        if context.mentioned_categories:
            patterns = [
                (r'\bthat category\b', f"the {context.mentioned_categories[-1]} category"),
                (r'\bthis category\b', f"the {context.mentioned_categories[-1]} category"),
            ]
            for pattern, replacement in patterns:
                resolved = re.sub(pattern, replacement, resolved, flags=re.IGNORECASE)

        # Goal references
        if context.mentioned_goals:
            patterns = [
                (r'\bthat goal\b', f"the {context.mentioned_goals[-1]} goal"),
                (r'\bthis goal\b', f"the {context.mentioned_goals[-1]} goal"),
            ]
            for pattern, replacement in patterns:
                resolved = re.sub(pattern, replacement, resolved, flags=re.IGNORECASE)

        # Pronoun "it" resolution based on active topic
        if context.active_topic:
            if context.active_topic == "subscription" and context.mentioned_subscriptions:
                resolved = re.sub(
                    r'\bit\b(?=\s|$|[.,!?])',
                    context.mentioned_subscriptions[-1],
                    resolved,
                    count=1,
                    flags=re.IGNORECASE
                )
            elif context.active_topic == "category" and context.mentioned_categories:
                resolved = re.sub(
                    r'\bit\b(?=\s|$|[.,!?])',
                    f"the {context.mentioned_categories[-1]} category",
                    resolved,
                    count=1,
                    flags=re.IGNORECASE
                )

        return resolved


# =============================================================================
# CONVERSATION MANAGER
# =============================================================================

class ConversationManager:
    """
    Manages conversation state and memory.
    Provides session management, context building, and entity tracking.
    """

    def __init__(self, ttl_seconds: int = 3600):
        """
        Initialize the conversation manager.

        Args:
            ttl_seconds: Time-to-live for sessions in seconds (default 1 hour)
        """
        self._sessions: Dict[str, ConversationContext] = {}
        self._ttl_seconds = ttl_seconds
        self._entity_extractor = EntityExtractor()
        self._reference_resolver = ReferenceResolver()

    def create_session(self, user_id: int, session_id: Optional[str] = None) -> ConversationContext:
        """
        Create a new conversation session.

        Args:
            user_id: User ID for the session
            session_id: Optional session ID (generated if not provided)

        Returns:
            New ConversationContext
        """
        if session_id is None:
            session_id = str(uuid.uuid4())

        context = ConversationContext(
            session_id=session_id,
            user_id=user_id
        )
        self._sessions[session_id] = context
        logger.info(f"Created session {session_id} for user {user_id}")
        return context

    def get_context(self, session_id: str) -> Optional[ConversationContext]:
        """
        Get conversation context by session ID.

        Args:
            session_id: Session ID to look up

        Returns:
            ConversationContext if found, None otherwise
        """
        context = self._sessions.get(session_id)
        if context:
            # Check if session has expired
            age = (datetime.utcnow() - context.last_activity).total_seconds()
            if age > self._ttl_seconds:
                logger.info(f"Session {session_id} expired")
                del self._sessions[session_id]
                return None
        return context

    def get_or_create_context(self, session_id: str, user_id: int) -> ConversationContext:
        """
        Get existing context or create a new one.

        Args:
            session_id: Session ID
            user_id: User ID (used if creating new session)

        Returns:
            ConversationContext
        """
        context = self.get_context(session_id)
        if context is None:
            context = self.create_session(user_id, session_id)
        return context

    def add_user_message(
        self,
        session_id: str,
        content: str,
        extract_entities: bool = True
    ) -> ConversationTurn:
        """
        Add a user message to the conversation.

        Args:
            session_id: Session ID
            content: Message content
            extract_entities: Whether to extract entities for reference tracking

        Returns:
            The created ConversationTurn
        """
        context = self._sessions.get(session_id)
        if not context:
            raise ValueError(f"Session {session_id} not found")

        turn = ConversationTurn(role="user", content=content)
        context.add_turn(turn)

        # Extract and track entities
        if extract_entities:
            entities = self._entity_extractor.extract(content)
            context.mentioned_subscriptions.extend(entities["subscriptions"])
            context.mentioned_categories.extend(entities["categories"])
            context.mentioned_amounts.extend(entities["amounts"])
            context.mentioned_goals.extend(entities["goals"])

            # Update active topic based on what was mentioned
            if entities["subscriptions"]:
                context.active_topic = "subscription"
            elif entities["categories"]:
                context.active_topic = "category"
            elif entities["goals"]:
                context.active_topic = "goal"

        return turn

    def add_assistant_message(
        self,
        session_id: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ConversationTurn:
        """
        Add an assistant message to the conversation.

        Args:
            session_id: Session ID
            content: Message content
            metadata: Optional metadata (e.g., visual payload info)

        Returns:
            The created ConversationTurn
        """
        context = self._sessions.get(session_id)
        if not context:
            raise ValueError(f"Session {session_id} not found")

        turn = ConversationTurn(
            role="assistant",
            content=content,
            metadata=metadata or {}
        )
        context.add_turn(turn)
        return turn

    def add_tool_call(
        self,
        session_id: str,
        tool_name: str,
        tool_args: Dict[str, Any],
        tool_result: Dict[str, Any],
        tool_call_id: str
    ) -> ConversationTurn:
        """
        Add a tool call result to the conversation.

        Args:
            session_id: Session ID
            tool_name: Name of the tool called
            tool_args: Arguments passed to the tool
            tool_result: Result from the tool
            tool_call_id: ID of the tool call

        Returns:
            The created ConversationTurn
        """
        context = self._sessions.get(session_id)
        if not context:
            raise ValueError(f"Session {session_id} not found")

        turn = ConversationTurn(
            role="tool",
            content=json.dumps(tool_result) if isinstance(tool_result, dict) else str(tool_result),
            tool_name=tool_name,
            tool_args=tool_args,
            tool_result=tool_result,
            tool_call_id=tool_call_id
        )
        context.add_turn(turn)
        return turn

    def resolve_references(self, session_id: str, message: str) -> str:
        """
        Resolve references in a message using conversation context.

        Args:
            session_id: Session ID
            message: Message with potential references

        Returns:
            Message with references resolved
        """
        context = self._sessions.get(session_id)
        if not context:
            return message

        return self._reference_resolver.resolve(message, context)

    def set_pending_confirmation(
        self,
        session_id: str,
        tool_name: str,
        params: Dict[str, Any],
        message: str
    ) -> None:
        """
        Set a pending confirmation for a tool execution.

        Args:
            session_id: Session ID
            tool_name: Tool awaiting confirmation
            params: Parameters for the tool
            message: Confirmation message shown to user
        """
        context = self._sessions.get(session_id)
        if context:
            context.pending_confirmation = {
                "tool_name": tool_name,
                "params": params,
                "message": message,
                "created_at": datetime.utcnow().isoformat()
            }

    def get_pending_confirmation(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get pending confirmation for a session."""
        context = self._sessions.get(session_id)
        if context:
            return context.pending_confirmation
        return None

    def clear_pending_confirmation(self, session_id: str) -> None:
        """Clear pending confirmation for a session."""
        context = self._sessions.get(session_id)
        if context:
            context.pending_confirmation = None

    def build_system_prompt(
        self,
        user_profile: Optional[Dict[str, Any]] = None,
        financial_summary: Optional[Dict[str, Any]] = None,
        user_id: Optional[int] = None
    ) -> str:
        """
        Build a system prompt with user context.

        Args:
            user_profile: User's financial profile
            financial_summary: Current financial state

        Returns:
            System prompt string
        """
        # Build user_id reference for tool calls
        uid_str = str(user_id) if user_id else "0"

        base_prompt = f"""You are BudgetBuddy, a friendly AI financial assistant. You help users understand their finances, track spending, and make smart money decisions.

CURRENT USER: The user's ID is {uid_str}. Use this ID when calling tools that require user_id.

## CONVERSATION GUIDELINES
- Be warm, helpful, and conversational
- Keep responses concise but informative (2-4 sentences for simple questions, more for analysis)
- For greetings like "hi", "hello", "hey" - just respond naturally and friendly, do NOT use any tools
- For general questions like "what can you do?" - explain your capabilities without using tools

## CRITICAL WORKFLOW FOR FINANCIAL QUESTIONS
When a user asks about their budget, spending, or finances, follow this workflow:

1. FIRST call check_user_setup_status with user_id={uid_str}
2. If is_fully_setup is false:
   - Guide them to complete setup first
   - DO NOT call budget/spending tools
3. If is_fully_setup is true:
   - Call the appropriate tool(s) to fetch their data
   - ANALYZE the data and provide intelligent insights (see Analysis Guidelines below)

## WHEN TO USE TOOLS
- check_user_setup_status: Call FIRST for any financial question (user_id={uid_str})
- suggest_next_action: When user needs onboarding guidance (user_id={uid_str})
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
   - "Your Dining Out spending ($X) is your 3rd highest category. Consider meal prepping 2 days a week to save $50-100/month"
   - "Shopping ($X) could be reduced by waiting 48 hours before non-essential purchases"

**For "can I afford X" questions:**
1. Call get_spending_status
2. Check dailyBudgetRemaining and daysRemaining
3. Calculate if the purchase fits within remaining budget
4. Give a clear yes/no with reasoning

**For "how am I doing" questions:**
1. Call get_spending_status
2. Look at status (under_budget, on_track, over_budget)
3. Explain their pace using specific numbers
4. If overspending, identify which categories are the culprits

**For budget overview requests:**
1. Call get_budget_overview
2. Explain the flow of money from income to categories
3. Highlight any concerning patterns (high % going to one category)

## DO NOT USE TOOLS FOR
- Greetings (hi, hello, hey)
- General questions (how are you, what can you do)
- Non-financial topics

## RESPONSE STYLE
- Be encouraging but honest about their financial situation
- ALWAYS use specific numbers from tool results
- Provide actionable, specific advice - not generic tips
- If recommending changes, estimate potential savings
- If setup is incomplete, focus on getting them set up"""

        # Add user context if available
        if user_profile:
            name = user_profile.get("name", "User")
            income = user_profile.get("monthly_income", 0)
            personality = user_profile.get("financial_personality", "balanced")
            goal = user_profile.get("primary_goal", "stability")

            base_prompt += f"""

## User Context
- Name: {name}
- Monthly Income: ${income:,.2f}
- Financial Personality: {personality}
- Primary Goal: {goal}"""

        if financial_summary:
            safe_to_spend = financial_summary.get("safe_to_spend", 0)
            spent = financial_summary.get("spent_this_month", 0)
            remaining = financial_summary.get("budget_remaining", 0)
            days_left = financial_summary.get("days_remaining", 0)

            base_prompt += f"""

## Current Financial State
- Safe to Spend: ${safe_to_spend:,.2f}
- Spent This Month: ${spent:,.2f}
- Budget Remaining: ${remaining:,.2f}
- Days Left in Month: {days_left}"""

        return base_prompt

    def end_session(self, session_id: str) -> bool:
        """
        End a conversation session.

        Args:
            session_id: Session ID to end

        Returns:
            True if session was found and ended, False otherwise
        """
        if session_id in self._sessions:
            del self._sessions[session_id]
            logger.info(f"Ended session {session_id}")
            return True
        return False

    def cleanup_expired_sessions(self) -> int:
        """
        Clean up expired sessions.

        Returns:
            Number of sessions cleaned up
        """
        now = datetime.utcnow()
        expired = [
            sid for sid, ctx in self._sessions.items()
            if (now - ctx.last_activity).total_seconds() > self._ttl_seconds
        ]
        for sid in expired:
            del self._sessions[sid]
        if expired:
            logger.info(f"Cleaned up {len(expired)} expired sessions")
        return len(expired)

    def get_session_count(self) -> int:
        """Get the number of active sessions."""
        return len(self._sessions)


# Singleton instance
_conversation_manager: Optional[ConversationManager] = None


def get_conversation_manager() -> ConversationManager:
    """Get the singleton conversation manager instance."""
    global _conversation_manager
    if _conversation_manager is None:
        _conversation_manager = ConversationManager()
    return _conversation_manager
