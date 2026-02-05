"""
Analytics Service for BudgetBuddy.
Tracks tool usage, agent performance, and user interactions.
"""

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class InteractionEvent:
    """Record of a user interaction with the agent."""
    user_id: int
    session_id: Optional[str]
    event_type: str  # "chat", "tool_call", "proactive", "upload"
    tool_name: Optional[str] = None
    success: bool = True
    latency_ms: float = 0
    feedback: Optional[str] = None  # "positive", "negative", None
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ToolStats:
    """Statistics for a single tool."""
    tool_name: str
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    total_latency_ms: float = 0
    last_called: Optional[datetime] = None

    @property
    def success_rate(self) -> float:
        if self.total_calls == 0:
            return 0.0
        return self.successful_calls / self.total_calls

    @property
    def avg_latency_ms(self) -> float:
        if self.total_calls == 0:
            return 0.0
        return self.total_latency_ms / self.total_calls

    def to_dict(self) -> Dict[str, Any]:
        return {
            "toolName": self.tool_name,
            "totalCalls": self.total_calls,
            "successfulCalls": self.successful_calls,
            "failedCalls": self.failed_calls,
            "successRate": round(self.success_rate * 100, 1),
            "avgLatencyMs": round(self.avg_latency_ms, 1),
            "lastCalled": self.last_called.isoformat() if self.last_called else None,
        }


@dataclass
class UserStats:
    """Statistics for a single user."""
    user_id: int
    total_interactions: int = 0
    total_tool_calls: int = 0
    sessions_count: int = 0
    last_active: Optional[datetime] = None
    favorite_tools: List[str] = field(default_factory=list)
    proactive_messages_shown: int = 0
    proactive_messages_acted: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "userId": self.user_id,
            "totalInteractions": self.total_interactions,
            "totalToolCalls": self.total_tool_calls,
            "sessionsCount": self.sessions_count,
            "lastActive": self.last_active.isoformat() if self.last_active else None,
            "favoriteTools": self.favorite_tools[:5],
            "proactiveEngagement": round(
                self.proactive_messages_acted / self.proactive_messages_shown * 100, 1
            ) if self.proactive_messages_shown > 0 else 0,
        }


class AgentAnalytics:
    """
    Analytics service for tracking agent performance and user interactions.
    """

    def __init__(self, max_events: int = 10000):
        """
        Initialize analytics service.

        Args:
            max_events: Maximum number of events to keep in memory
        """
        self._events: List[InteractionEvent] = []
        self._max_events = max_events
        self._tool_stats: Dict[str, ToolStats] = {}
        self._user_stats: Dict[int, UserStats] = {}
        self._daily_counts: Dict[str, int] = defaultdict(int)
        self._hourly_counts: Dict[str, int] = defaultdict(int)

    def log_interaction(self, event: InteractionEvent) -> None:
        """Log an interaction event."""
        # Add to event list
        self._events.append(event)

        # Trim if necessary
        if len(self._events) > self._max_events:
            self._events = self._events[-self._max_events:]

        # Update tool stats
        if event.tool_name:
            self._update_tool_stats(event)

        # Update user stats
        self._update_user_stats(event)

        # Update time-based counts
        date_key = event.timestamp.strftime("%Y-%m-%d")
        hour_key = event.timestamp.strftime("%Y-%m-%d-%H")
        self._daily_counts[date_key] += 1
        self._hourly_counts[hour_key] += 1

        logger.debug(f"Logged event: {event.event_type} for user {event.user_id}")

    def log_chat(
        self,
        user_id: int,
        session_id: Optional[str],
        latency_ms: float,
        tool_name: Optional[str] = None,
        success: bool = True
    ) -> None:
        """Convenience method to log a chat interaction."""
        self.log_interaction(InteractionEvent(
            user_id=user_id,
            session_id=session_id,
            event_type="chat",
            tool_name=tool_name,
            success=success,
            latency_ms=latency_ms
        ))

    def log_tool_call(
        self,
        user_id: int,
        session_id: Optional[str],
        tool_name: str,
        success: bool,
        latency_ms: float,
        error: Optional[str] = None
    ) -> None:
        """Log a tool execution."""
        self.log_interaction(InteractionEvent(
            user_id=user_id,
            session_id=session_id,
            event_type="tool_call",
            tool_name=tool_name,
            success=success,
            latency_ms=latency_ms,
            metadata={"error": error} if error else {}
        ))

    def log_proactive_message(
        self,
        user_id: int,
        condition_id: str,
        was_acted_upon: bool = False
    ) -> None:
        """Log a proactive message shown to user."""
        self.log_interaction(InteractionEvent(
            user_id=user_id,
            session_id=None,
            event_type="proactive",
            success=True,
            metadata={
                "condition_id": condition_id,
                "was_acted_upon": was_acted_upon
            }
        ))

        # Update user proactive stats
        if user_id in self._user_stats:
            self._user_stats[user_id].proactive_messages_shown += 1
            if was_acted_upon:
                self._user_stats[user_id].proactive_messages_acted += 1

    def _update_tool_stats(self, event: InteractionEvent) -> None:
        """Update statistics for a tool."""
        tool_name = event.tool_name
        if not tool_name:
            return

        if tool_name not in self._tool_stats:
            self._tool_stats[tool_name] = ToolStats(tool_name=tool_name)

        stats = self._tool_stats[tool_name]
        stats.total_calls += 1
        stats.total_latency_ms += event.latency_ms
        stats.last_called = event.timestamp

        if event.success:
            stats.successful_calls += 1
        else:
            stats.failed_calls += 1

    def _update_user_stats(self, event: InteractionEvent) -> None:
        """Update statistics for a user."""
        user_id = event.user_id
        if user_id not in self._user_stats:
            self._user_stats[user_id] = UserStats(user_id=user_id)

        stats = self._user_stats[user_id]
        stats.total_interactions += 1
        stats.last_active = event.timestamp

        if event.event_type == "tool_call":
            stats.total_tool_calls += 1
            if event.tool_name:
                # Track favorite tools
                if event.tool_name not in stats.favorite_tools:
                    stats.favorite_tools.append(event.tool_name)

    def get_tool_stats(self) -> Dict[str, Any]:
        """Get statistics for all tools."""
        return {
            name: stats.to_dict()
            for name, stats in sorted(
                self._tool_stats.items(),
                key=lambda x: -x[1].total_calls
            )
        }

    def get_tool_success_rates(self) -> Dict[str, float]:
        """Get success rate by tool."""
        return {
            name: round(stats.success_rate * 100, 1)
            for name, stats in self._tool_stats.items()
        }

    def get_user_stats(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get statistics for a specific user."""
        if user_id in self._user_stats:
            return self._user_stats[user_id].to_dict()
        return None

    def get_overview(self, days: int = 7) -> Dict[str, Any]:
        """
        Get analytics overview.

        Args:
            days: Number of days to include in overview

        Returns:
            Dict with overview statistics
        """
        cutoff = datetime.utcnow() - timedelta(days=days)
        recent_events = [e for e in self._events if e.timestamp > cutoff]

        # Count by type
        type_counts = defaultdict(int)
        for event in recent_events:
            type_counts[event.event_type] += 1

        # Success rate
        successful = sum(1 for e in recent_events if e.success)
        success_rate = (successful / len(recent_events) * 100) if recent_events else 0

        # Average latency
        latencies = [e.latency_ms for e in recent_events if e.latency_ms > 0]
        avg_latency = sum(latencies) / len(latencies) if latencies else 0

        # Daily activity
        daily_activity = []
        for i in range(days):
            date = (datetime.utcnow() - timedelta(days=i)).strftime("%Y-%m-%d")
            daily_activity.append({
                "date": date,
                "count": self._daily_counts.get(date, 0)
            })
        daily_activity.reverse()

        # Top tools
        top_tools = sorted(
            self._tool_stats.values(),
            key=lambda x: -x.total_calls
        )[:5]

        # Active users
        active_users = sum(
            1 for stats in self._user_stats.values()
            if stats.last_active and stats.last_active > cutoff
        )

        return {
            "period": f"Last {days} days",
            "totalEvents": len(recent_events),
            "eventsByType": dict(type_counts),
            "successRate": round(success_rate, 1),
            "avgLatencyMs": round(avg_latency, 1),
            "activeUsers": active_users,
            "totalUsers": len(self._user_stats),
            "dailyActivity": daily_activity,
            "topTools": [t.to_dict() for t in top_tools],
        }

    def get_common_failure_patterns(self) -> List[Dict[str, Any]]:
        """Identify common failure patterns for improvement."""
        failures = [e for e in self._events if not e.success]

        # Group by tool and error
        patterns: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for event in failures:
            tool = event.tool_name or "unknown"
            error = event.metadata.get("error", "unknown_error")
            patterns[tool][error] += 1

        # Convert to list
        result = []
        for tool, errors in patterns.items():
            for error, count in errors.items():
                result.append({
                    "tool": tool,
                    "error": error,
                    "count": count,
                    "suggestion": self._get_improvement_suggestion(tool, error)
                })

        return sorted(result, key=lambda x: -x["count"])[:10]

    def _get_improvement_suggestion(self, tool: str, error: str) -> str:
        """Generate improvement suggestion for a failure pattern."""
        if "timeout" in error.lower():
            return "Consider increasing timeout or optimizing tool performance"
        if "not found" in error.lower():
            return "Improve tool parameter validation or user guidance"
        if "permission" in error.lower() or "auth" in error.lower():
            return "Review authentication requirements"
        return "Investigate root cause and add error handling"

    def clear(self) -> None:
        """Clear all analytics data."""
        self._events.clear()
        self._tool_stats.clear()
        self._user_stats.clear()
        self._daily_counts.clear()
        self._hourly_counts.clear()


# Singleton instance
_analytics: Optional[AgentAnalytics] = None


def get_analytics() -> AgentAnalytics:
    """Get the singleton analytics instance."""
    global _analytics
    if _analytics is None:
        _analytics = AgentAnalytics()
    return _analytics
