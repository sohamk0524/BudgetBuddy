"""
Profile Health Engine for BudgetBuddy.
Monitors user state and triggers proactive agent behaviors.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple
from functools import wraps

logger = logging.getLogger(__name__)


# =============================================================================
# ENUMS AND DATA CLASSES
# =============================================================================

class Severity(str, Enum):
    """Severity levels for state conditions."""
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


@dataclass
class StateCondition:
    """
    Defines a detectable user state that may trigger agent intervention.
    """
    # Identity
    condition_id: str
    name: str
    severity: Severity

    # Detection
    check_function: str  # Name of the checker function
    check_query: Optional[str] = None  # Optional SQL query for data-driven checks

    # Response
    trigger_message: str = ""  # What the agent says (supports {placeholders})
    suggested_tool: Optional[str] = None  # Tool to offer/execute
    requires_confirmation: bool = True  # Ask before acting?

    # Rate limiting
    cooldown_hours: int = 24  # Minimum hours between triggers
    max_triggers_per_week: int = 3  # Prevent nagging

    # Context
    priority: int = 50  # Higher = check first (0-100)
    supersedes: List[str] = field(default_factory=list)  # Conditions this overrides

    # Additional context for trigger message
    context_keys: List[str] = field(default_factory=list)  # Expected context keys


@dataclass
class CheckResult:
    """Result from a condition checker."""
    triggered: bool
    context: Dict[str, Any] = field(default_factory=dict)  # Dynamic values for message template
    message_override: Optional[str] = None  # Optional custom message


@dataclass
class TriggeredCondition:
    """A condition that was triggered for a user."""
    condition: StateCondition
    context: Dict[str, Any]
    triggered_at: datetime = field(default_factory=datetime.utcnow)

    def format_message(self) -> str:
        """Format the trigger message with context values."""
        try:
            return self.condition.trigger_message.format(**self.context)
        except KeyError as e:
            logger.warning(f"Missing context key for message template: {e}")
            return self.condition.trigger_message


@dataclass
class HealthAssessment:
    """Full health assessment for a user."""
    user_id: int
    triggered_conditions: List[TriggeredCondition]
    health_score: int  # 0-100, higher is better
    summary: str
    assessed_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class AgentContext:
    """Context passed to the agent for proactive behaviors."""
    greeting_override: Optional[str] = None
    suggested_actions: List[str] = field(default_factory=list)
    health_summary: Optional[str] = None
    triggered_conditions: List[TriggeredCondition] = field(default_factory=list)
    priority_condition: Optional[TriggeredCondition] = None


# =============================================================================
# CONDITION CHECKER REGISTRY
# =============================================================================

# Registry of checker functions
_CHECKERS: Dict[str, Callable] = {}


def register_checker(name: str):
    """Decorator to register a condition checker function."""
    def decorator(func: Callable):
        _CHECKERS[name] = func
        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        return wrapper
    return decorator


def get_checker(name: str) -> Optional[Callable]:
    """Get a checker function by name."""
    return _CHECKERS.get(name)


# =============================================================================
# CONDITION CHECKERS
# =============================================================================

@register_checker("check_no_plan")
def check_no_plan(db_session, user_id: int) -> CheckResult:
    """Check if user has no budget plan."""
    try:
        from db_models import BudgetPlan
        plan = BudgetPlan.query.filter_by(user_id=user_id).first()
        if plan is None:
            return CheckResult(triggered=True, context={"reason": "no_plan_exists"})
        return CheckResult(triggered=False)
    except Exception as e:
        logger.error(f"Error checking plan for user {user_id}: {e}")
        return CheckResult(triggered=False)


@register_checker("check_no_profile")
def check_no_profile(db_session, user_id: int) -> CheckResult:
    """Check if user has no financial profile."""
    try:
        from db_models import FinancialProfile
        profile = FinancialProfile.query.filter_by(user_id=user_id).first()
        if profile is None:
            return CheckResult(triggered=True, context={"reason": "no_profile_exists"})
        # Check if profile is incomplete
        if profile.monthly_income is None or profile.monthly_income == 0:
            return CheckResult(triggered=True, context={"reason": "profile_incomplete"})
        return CheckResult(triggered=False)
    except Exception as e:
        logger.error(f"Error checking profile for user {user_id}: {e}")
        return CheckResult(triggered=False)


@register_checker("check_spending_velocity")
def check_spending_velocity(db_session, user_id: int) -> CheckResult:
    """Check if user is spending too fast."""
    try:
        from services.data_mock import get_spending_status_data
        data = get_spending_status_data()

        spent = data.get("spent", 0)
        budget = data.get("budget", 1)
        day_of_month = data.get("dayOfMonth", 1)

        # Calculate expected spending for this day of month
        expected_percent = (day_of_month / 30) * 100
        actual_percent = (spent / budget) * 100

        # Trigger if spending more than 20% ahead of pace
        if actual_percent > expected_percent + 20:
            return CheckResult(
                triggered=True,
                context={
                    "percent_of_budget": round(actual_percent, 1),
                    "days_elapsed": day_of_month,
                    "spent": spent,
                    "budget": budget
                }
            )
        return CheckResult(triggered=False)
    except Exception as e:
        logger.error(f"Error checking spending velocity for user {user_id}: {e}")
        return CheckResult(triggered=False)


@register_checker("check_under_budget")
def check_under_budget(db_session, user_id: int) -> CheckResult:
    """Check if user is significantly under budget (positive milestone)."""
    try:
        from services.data_mock import get_spending_status_data, SAVINGS_GOALS
        data = get_spending_status_data()

        spent = data.get("spent", 0)
        budget = data.get("budget", 1)
        day_of_month = data.get("dayOfMonth", 1)

        # Only check after day 15 of month
        if day_of_month < 15:
            return CheckResult(triggered=False)

        expected_percent = (day_of_month / 30) * 100
        actual_percent = (spent / budget) * 100

        # Trigger if spending more than 15% below pace
        if actual_percent < expected_percent - 15:
            amount_saved = (budget * (expected_percent / 100)) - spent
            top_goal = SAVINGS_GOALS[0]["name"] if SAVINGS_GOALS else "savings"

            return CheckResult(
                triggered=True,
                context={
                    "percent_under": round(expected_percent - actual_percent, 1),
                    "amount": round(amount_saved, 2),
                    "top_goal": top_goal
                }
            )
        return CheckResult(triggered=False)
    except Exception as e:
        logger.error(f"Error checking under budget for user {user_id}: {e}")
        return CheckResult(triggered=False)


@register_checker("check_goal_progress")
def check_goal_progress(db_session, user_id: int) -> CheckResult:
    """Check if any savings goal is behind schedule."""
    try:
        from services.data_mock import get_savings_progress_data
        data = get_savings_progress_data()

        goals = data.get("goals", [])
        for goal in goals:
            progress = goal.get("progress_percent", 0)
            # Simple heuristic: if a goal is less than 50% complete and has been active
            # This would ideally check against a target date
            if progress < 30 and goal.get("target", 0) > 1000:
                remaining = goal["target"] - goal["current"]
                return CheckResult(
                    triggered=True,
                    context={
                        "goal_name": goal["name"],
                        "percent_behind": round(50 - progress, 1),
                        "months_late": 2,  # Simplified
                        "remaining": remaining
                    }
                )
        return CheckResult(triggered=False)
    except Exception as e:
        logger.error(f"Error checking goal progress for user {user_id}: {e}")
        return CheckResult(triggered=False)


@register_checker("check_goal_milestones")
def check_goal_milestones(db_session, user_id: int) -> CheckResult:
    """Check if any savings goal has hit a milestone."""
    try:
        from services.data_mock import get_savings_progress_data
        data = get_savings_progress_data()

        goals = data.get("goals", [])
        milestones = [25, 50, 75, 90]

        for goal in goals:
            progress = goal.get("progress_percent", 0)
            for milestone in milestones:
                # Check if progress is within 2% of a milestone
                if abs(progress - milestone) < 2:
                    return CheckResult(
                        triggered=True,
                        context={
                            "milestone": milestone,
                            "goal_name": goal["name"],
                            "remaining": goal["target"] - goal["current"]
                        }
                    )
        return CheckResult(triggered=False)
    except Exception as e:
        logger.error(f"Error checking goal milestones for user {user_id}: {e}")
        return CheckResult(triggered=False)


@register_checker("check_stale_plan")
def check_stale_plan(db_session, user_id: int) -> CheckResult:
    """Check if user's plan is outdated."""
    try:
        from db_models import BudgetPlan
        plan = BudgetPlan.query.filter_by(user_id=user_id).order_by(BudgetPlan.created_at.desc()).first()

        if plan is None:
            return CheckResult(triggered=False)  # Handled by check_no_plan

        # Check if plan is older than 30 days
        age = datetime.utcnow() - plan.created_at
        if age > timedelta(days=30):
            return CheckResult(
                triggered=True,
                context={
                    "days_old": age.days,
                    "created_month": plan.month_year
                }
            )
        return CheckResult(triggered=False)
    except Exception as e:
        logger.error(f"Error checking stale plan for user {user_id}: {e}")
        return CheckResult(triggered=False)


# =============================================================================
# STATE CONDITIONS REGISTRY
# =============================================================================

# Default state conditions
DEFAULT_STATE_CONDITIONS: List[StateCondition] = [
    # Critical conditions
    StateCondition(
        condition_id="no_financial_profile",
        name="Incomplete Onboarding",
        severity=Severity.CRITICAL,
        check_function="check_no_profile",
        trigger_message="To give you personalized advice, I need to know a bit about your financial situation. Can we take 2 minutes to set up your profile?",
        suggested_tool="initiate_onboarding",
        requires_confirmation=True,
        cooldown_hours=48,
        max_triggers_per_week=2,
        priority=100,
        supersedes=["no_budget_plan", "stale_plan"]
    ),

    StateCondition(
        condition_id="no_budget_plan",
        name="Missing Budget Plan",
        severity=Severity.CRITICAL,
        check_function="check_no_plan",
        trigger_message="I noticed you haven't created a budget plan yet. A personalized plan can help you track spending and reach your goals faster. Would you like to build one together?",
        suggested_tool="create_budget_plan",
        requires_confirmation=True,
        cooldown_hours=24,
        max_triggers_per_week=3,
        priority=90,
        supersedes=["stale_plan"]
    ),

    # Warning conditions
    StateCondition(
        condition_id="spending_velocity_high",
        name="Overspending Alert",
        severity=Severity.WARNING,
        check_function="check_spending_velocity",
        trigger_message="Heads up — you've spent {percent_of_budget}% of your monthly budget and we're only {days_elapsed} days in. Want me to show you where the money's going?",
        suggested_tool="get_spending_status",
        requires_confirmation=False,
        cooldown_hours=72,
        max_triggers_per_week=2,
        priority=80,
        context_keys=["percent_of_budget", "days_elapsed"]
    ),

    StateCondition(
        condition_id="goal_at_risk",
        name="Savings Goal Behind Schedule",
        severity=Severity.WARNING,
        check_function="check_goal_progress",
        trigger_message="Your '{goal_name}' goal is {percent_behind}% behind schedule. Should we look at ways to catch up?",
        suggested_tool="get_savings_progress",
        requires_confirmation=True,
        cooldown_hours=168,
        max_triggers_per_week=1,
        priority=70,
        context_keys=["goal_name", "percent_behind"]
    ),

    StateCondition(
        condition_id="stale_plan",
        name="Outdated Budget Plan",
        severity=Severity.WARNING,
        check_function="check_stale_plan",
        trigger_message="Your budget plan is {days_old} days old. Your finances may have changed — would you like to create an updated plan?",
        suggested_tool="create_budget_plan",
        requires_confirmation=True,
        cooldown_hours=168,
        max_triggers_per_week=1,
        priority=60,
        context_keys=["days_old"]
    ),

    # Info conditions (positive reinforcement)
    StateCondition(
        condition_id="under_budget_milestone",
        name="Under Budget Achievement",
        severity=Severity.INFO,
        check_function="check_under_budget",
        trigger_message="Great news! You're {percent_under}% under budget this month. You could put that extra ${amount} toward your {top_goal} goal!",
        suggested_tool=None,
        requires_confirmation=False,
        cooldown_hours=168,
        max_triggers_per_week=1,
        priority=30,
        context_keys=["percent_under", "amount", "top_goal"]
    ),

    StateCondition(
        condition_id="goal_milestone_reached",
        name="Savings Milestone",
        severity=Severity.INFO,
        check_function="check_goal_milestones",
        trigger_message="Congratulations! You've hit {milestone}% of your '{goal_name}' goal! Keep it up — only ${remaining:,.2f} to go.",
        suggested_tool=None,
        requires_confirmation=False,
        cooldown_hours=168,
        max_triggers_per_week=2,
        priority=20,
        context_keys=["milestone", "goal_name", "remaining"]
    ),
]


# =============================================================================
# PROFILE HEALTH ENGINE
# =============================================================================

class ProfileHealthEngine:
    """
    Monitors user state and triggers proactive agent behaviors.
    """

    def __init__(
        self,
        conditions: Optional[List[StateCondition]] = None,
        db_session: Any = None
    ):
        """
        Initialize the health engine.

        Args:
            conditions: List of state conditions to monitor (defaults to DEFAULT_STATE_CONDITIONS)
            db_session: Database session for queries
        """
        self.conditions = sorted(
            conditions or DEFAULT_STATE_CONDITIONS,
            key=lambda c: -c.priority  # Sort by priority descending
        )
        self.db = db_session

        # Track when conditions were last triggered per user
        self._trigger_history: Dict[int, Dict[str, List[datetime]]] = {}

    def assess_user_health(self, user_id: int) -> HealthAssessment:
        """
        Evaluate all conditions for a user.

        Args:
            user_id: User ID to assess

        Returns:
            HealthAssessment with triggered conditions and health score
        """
        triggered: List[TriggeredCondition] = []
        superseded_ids: set = set()
        checks_passed = 0
        total_checks = len(self.conditions)

        for condition in self.conditions:
            # Skip superseded conditions
            if condition.condition_id in superseded_ids:
                continue

            # Check cooldown
            if self._is_on_cooldown(user_id, condition):
                checks_passed += 1
                continue

            # Run the check
            result = self._check_condition(user_id, condition)

            if result.triggered:
                triggered.append(TriggeredCondition(
                    condition=condition,
                    context=result.context
                ))
                superseded_ids.update(condition.supersedes)

                # Record trigger
                self._record_trigger(user_id, condition.condition_id)
            else:
                checks_passed += 1

        # Calculate health score (0-100)
        health_score = int((checks_passed / total_checks) * 100) if total_checks > 0 else 100

        # Generate summary
        if not triggered:
            summary = "Your financial health looks great! No issues detected."
        elif triggered[0].condition.severity == Severity.CRITICAL:
            summary = f"Attention needed: {triggered[0].condition.name}"
        elif triggered[0].condition.severity == Severity.WARNING:
            summary = f"Heads up: {len(triggered)} item(s) need your attention."
        else:
            summary = f"Good news: {triggered[0].condition.name}"

        return HealthAssessment(
            user_id=user_id,
            triggered_conditions=triggered,
            health_score=health_score,
            summary=summary
        )

    def get_greeting_context(self, user_id: int) -> AgentContext:
        """
        Get context for agent's opening message.
        Called on session start.

        Args:
            user_id: User ID

        Returns:
            AgentContext with greeting override and suggestions
        """
        assessment = self.assess_user_health(user_id)

        if not assessment.triggered_conditions:
            return AgentContext(
                greeting_override=None,
                suggested_actions=[],
                health_summary=assessment.summary
            )

        # Get highest priority triggered condition
        top_condition = assessment.triggered_conditions[0]

        # Build suggested actions from all triggered conditions
        suggested_actions = [
            tc.condition.suggested_tool
            for tc in assessment.triggered_conditions
            if tc.condition.suggested_tool
        ]

        return AgentContext(
            greeting_override=top_condition.format_message(),
            suggested_actions=suggested_actions,
            health_summary=assessment.summary,
            triggered_conditions=assessment.triggered_conditions,
            priority_condition=top_condition
        )

    def get_proactive_message(self, user_id: int) -> Optional[str]:
        """
        Get a proactive message for the user if any conditions are triggered.

        Args:
            user_id: User ID

        Returns:
            Message string or None
        """
        context = self.get_greeting_context(user_id)
        return context.greeting_override

    def _check_condition(self, user_id: int, condition: StateCondition) -> CheckResult:
        """Execute the check function for a condition."""
        checker = get_checker(condition.check_function)
        if not checker:
            logger.warning(f"No checker found for: {condition.check_function}")
            return CheckResult(triggered=False)

        try:
            return checker(self.db, user_id)
        except Exception as e:
            logger.error(f"Checker {condition.check_function} failed: {e}")
            return CheckResult(triggered=False)

    def _is_on_cooldown(self, user_id: int, condition: StateCondition) -> bool:
        """Check if a condition is on cooldown for a user."""
        history = self._trigger_history.get(user_id, {})
        triggers = history.get(condition.condition_id, [])

        if not triggers:
            return False

        # Check cooldown
        last_trigger = triggers[-1]
        cooldown_end = last_trigger + timedelta(hours=condition.cooldown_hours)
        if datetime.utcnow() < cooldown_end:
            return True

        # Check weekly limit
        week_ago = datetime.utcnow() - timedelta(days=7)
        recent_triggers = [t for t in triggers if t > week_ago]
        if len(recent_triggers) >= condition.max_triggers_per_week:
            return True

        return False

    def _record_trigger(self, user_id: int, condition_id: str) -> None:
        """Record that a condition was triggered."""
        if user_id not in self._trigger_history:
            self._trigger_history[user_id] = {}
        if condition_id not in self._trigger_history[user_id]:
            self._trigger_history[user_id][condition_id] = []

        self._trigger_history[user_id][condition_id].append(datetime.utcnow())

        # Keep only last 10 triggers per condition
        self._trigger_history[user_id][condition_id] = \
            self._trigger_history[user_id][condition_id][-10:]

    def add_condition(self, condition: StateCondition) -> None:
        """Add a new condition to monitor."""
        self.conditions.append(condition)
        self.conditions.sort(key=lambda c: -c.priority)
        logger.info(f"Added state condition: {condition.condition_id}")

    def remove_condition(self, condition_id: str) -> bool:
        """Remove a condition by ID."""
        initial_len = len(self.conditions)
        self.conditions = [c for c in self.conditions if c.condition_id != condition_id]
        removed = len(self.conditions) < initial_len
        if removed:
            logger.info(f"Removed state condition: {condition_id}")
        return removed


# Singleton instance
_health_engine: Optional[ProfileHealthEngine] = None


def get_health_engine() -> ProfileHealthEngine:
    """Get the singleton health engine instance."""
    global _health_engine
    if _health_engine is None:
        _health_engine = ProfileHealthEngine()
    return _health_engine
