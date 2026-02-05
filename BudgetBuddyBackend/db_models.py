"""
Database models for BudgetBuddy authentication and user profiles.
Uses SQLAlchemy for ORM with SQLite database.
"""

from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class User(db.Model):
    """User account for authentication."""
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    profile = db.relationship('FinancialProfile', backref='user', uselist=False)
    statement = db.relationship('SavedStatement', backref='user', uselist=False)


class FinancialProfile(db.Model):
    """User's financial profile from onboarding."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    # General profile fields (from onboarding)
    age = db.Column(db.Integer)  # User's age
    occupation = db.Column(db.String(30))  # "student", "employed", "self_employed", "retired"
    monthly_income = db.Column(db.Float, default=0.0)
    income_frequency = db.Column(db.String(20))  # "biweekly", "monthly", "irregular"
    financial_personality = db.Column(db.String(30))  # "aggressive_saver", "balanced", "paycheck_to_paycheck"
    primary_goal = db.Column(db.String(30))  # "emergency_fund", "pay_debt", "save_purchase", "stability"

    # Legacy fields (kept for backward compatibility, now collected during plan creation)
    fixed_expenses = db.Column(db.Float, default=0.0)
    savings_goal_name = db.Column(db.String(100))
    savings_goal_target = db.Column(db.Float, default=0.0)
    housing_situation = db.Column(db.String(20))  # "rent", "own", "family"
    debt_types = db.Column(db.String(200))  # JSON array: ["student_loans", "credit_cards", "car"]


class BudgetPlan(db.Model):
    """Generated spending plan for a user."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    plan_json = db.Column(db.Text, nullable=False)  # Full plan as JSON
    created_at = db.Column(db.DateTime, default=db.func.now())
    month_year = db.Column(db.String(7))  # "2026-02" format

    user = db.relationship('User', backref='budget_plans')


class SavedStatement(db.Model):
    """
    User's saved bank statement with parsed data and analysis.
    Each user has at most one saved statement (new uploads replace old).
    """
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, unique=True)

    # Original file info
    filename = db.Column(db.String(255), nullable=False)
    file_type = db.Column(db.String(10), nullable=False)  # "pdf" or "csv"
    raw_file = db.Column(db.LargeBinary, nullable=False)  # Original file bytes

    # Parsed and analyzed data (stored as JSON strings)
    parsed_data = db.Column(db.Text)  # JSON: extracted transactions and metadata
    llm_analysis = db.Column(db.Text)  # JSON: full LLM response

    # Derived financial metrics (for quick access without parsing JSON)
    ending_balance = db.Column(db.Float, default=0.0)
    total_income = db.Column(db.Float, default=0.0)
    total_expenses = db.Column(db.Float, default=0.0)
    statement_start_date = db.Column(db.Date)
    statement_end_date = db.Column(db.Date)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ConversationSession(db.Model):
    """
    A conversation session between a user and the AI agent.
    Sessions persist across multiple messages until explicitly ended or expired.
    """
    id = db.Column(db.String(36), primary_key=True)  # UUID
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    # Session state
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_activity = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    ended_at = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, default=True)

    # Context storage (JSON)
    context_json = db.Column(db.Text)  # Serialized conversation context

    # Extracted entities for reference resolution (JSON arrays)
    mentioned_subscriptions = db.Column(db.Text)  # JSON array
    mentioned_categories = db.Column(db.Text)  # JSON array
    mentioned_goals = db.Column(db.Text)  # JSON array
    mentioned_amounts = db.Column(db.Text)  # JSON array

    # Conversation state
    active_topic = db.Column(db.String(50))  # Current topic focus
    pending_confirmation = db.Column(db.Text)  # JSON: pending action awaiting confirmation

    # Relationships
    user = db.relationship('User', backref='conversation_sessions')
    turns = db.relationship('ConversationTurn', backref='session', lazy='dynamic',
                           order_by='ConversationTurn.created_at')


class ConversationTurn(db.Model):
    """
    A single turn (message) in a conversation session.
    Supports user messages, assistant responses, and tool calls.
    """
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(36), db.ForeignKey('conversation_session.id'), nullable=False)

    # Message content
    role = db.Column(db.String(20), nullable=False)  # "user", "assistant", "system", "tool"
    content = db.Column(db.Text, nullable=False)

    # Tool call information (for tool role)
    tool_name = db.Column(db.String(100))
    tool_args = db.Column(db.Text)  # JSON
    tool_result = db.Column(db.Text)  # JSON
    tool_call_id = db.Column(db.String(100))

    # Metadata
    metadata_json = db.Column(db.Text)  # JSON: additional metadata (visual payload, etc.)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class StateConditionTrigger(db.Model):
    """
    Record of when a state condition was triggered for a user.
    Used for cooldown tracking and analytics.
    """
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    # Condition info
    condition_id = db.Column(db.String(100), nullable=False)
    condition_name = db.Column(db.String(200))
    severity = db.Column(db.String(20))  # "critical", "warning", "info"

    # Trigger context
    trigger_context = db.Column(db.Text)  # JSON: context values at trigger time
    message_shown = db.Column(db.Text)  # The actual message shown to user

    # User response
    was_dismissed = db.Column(db.Boolean, default=False)
    was_acted_upon = db.Column(db.Boolean, default=False)
    action_taken = db.Column(db.String(100))  # Tool used if acted upon

    # Timestamps
    triggered_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    user = db.relationship('User', backref='condition_triggers')


class ToolExecution(db.Model):
    """
    Record of tool executions for analytics and debugging.
    """
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    session_id = db.Column(db.String(36), db.ForeignKey('conversation_session.id'), nullable=True)

    # Tool info
    tool_name = db.Column(db.String(100), nullable=False)
    tool_args = db.Column(db.Text)  # JSON

    # Execution result
    success = db.Column(db.Boolean, nullable=False)
    error_message = db.Column(db.Text)
    error_code = db.Column(db.String(50))

    # Performance
    duration_ms = db.Column(db.Float)

    # Output
    result_data = db.Column(db.Text)  # JSON (truncated for large results)
    has_visual = db.Column(db.Boolean, default=False)
    visual_type = db.Column(db.String(50))

    # Timestamps
    executed_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    user = db.relationship('User', backref='tool_executions')
    session = db.relationship('ConversationSession', backref='tool_executions')


class Transaction(db.Model):
    """
    Individual financial transaction (expense or income).
    Can be manually entered or imported from statements.
    """
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    # Transaction details
    amount = db.Column(db.Float, nullable=False)
    transaction_type = db.Column(db.String(20), nullable=False)  # "expense", "income"
    category = db.Column(db.String(50), nullable=False)
    merchant = db.Column(db.String(200))
    description = db.Column(db.Text)

    # Date and source
    transaction_date = db.Column(db.Date, nullable=False)
    source = db.Column(db.String(20), default="manual")  # "manual", "statement", "recurring"

    # For recurring transactions
    is_recurring = db.Column(db.Boolean, default=False)
    recurring_id = db.Column(db.Integer, db.ForeignKey('recurring_transaction.id'), nullable=True)

    # Metadata
    tags = db.Column(db.Text)  # JSON array of tags
    notes = db.Column(db.Text)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = db.relationship('User', backref='transactions')


class RecurringTransaction(db.Model):
    """
    Template for recurring transactions (subscriptions, bills, etc.).
    """
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    # Transaction template
    name = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    merchant = db.Column(db.String(200))

    # Recurrence settings
    frequency = db.Column(db.String(20), nullable=False)  # "weekly", "biweekly", "monthly", "yearly"
    day_of_month = db.Column(db.Integer)  # For monthly
    day_of_week = db.Column(db.Integer)  # For weekly (0=Monday)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date)  # Null = no end

    # Status
    is_active = db.Column(db.Boolean, default=True)
    last_generated = db.Column(db.Date)
    next_due = db.Column(db.Date)

    # Metadata
    notes = db.Column(db.Text)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = db.relationship('User', backref='recurring_transactions')
    transactions = db.relationship('Transaction', backref='recurring_source')


class SavingsGoal(db.Model):
    """
    User's savings goal with target amount and progress tracking.
    """
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    # Goal details
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    target_amount = db.Column(db.Float, nullable=False)
    current_amount = db.Column(db.Float, default=0.0)

    # Timeline
    target_date = db.Column(db.Date)
    start_date = db.Column(db.Date, default=datetime.utcnow)

    # Status
    is_active = db.Column(db.Boolean, default=True)
    is_completed = db.Column(db.Boolean, default=False)
    completed_at = db.Column(db.DateTime)

    # Contribution settings
    monthly_contribution = db.Column(db.Float, default=0.0)
    auto_contribute = db.Column(db.Boolean, default=False)

    # Category/priority
    priority = db.Column(db.Integer, default=1)  # 1=high, 2=medium, 3=low
    icon = db.Column(db.String(50))  # Emoji or icon name

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = db.relationship('User', backref='savings_goals')
    contributions = db.relationship('SavingsContribution', backref='goal', lazy='dynamic')


class SavingsContribution(db.Model):
    """
    Record of a contribution to a savings goal.
    """
    id = db.Column(db.Integer, primary_key=True)
    goal_id = db.Column(db.Integer, db.ForeignKey('savings_goal.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    # Contribution details
    amount = db.Column(db.Float, nullable=False)
    contribution_date = db.Column(db.Date, nullable=False)
    source = db.Column(db.String(50))  # "manual", "auto", "transfer"
    notes = db.Column(db.Text)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    user = db.relationship('User', backref='savings_contributions')


class BudgetCategory(db.Model):
    """
    Budget allocation for a specific category.
    Part of a user's budget plan.
    """
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    plan_id = db.Column(db.Integer, db.ForeignKey('budget_plan.id'), nullable=True)

    # Category details
    name = db.Column(db.String(50), nullable=False)
    budgeted_amount = db.Column(db.Float, nullable=False)
    spent_amount = db.Column(db.Float, default=0.0)

    # Category type
    category_type = db.Column(db.String(20), default="variable")  # "fixed", "variable", "savings"
    is_essential = db.Column(db.Boolean, default=False)

    # Display
    icon = db.Column(db.String(50))
    color = db.Column(db.String(20))
    display_order = db.Column(db.Integer, default=0)

    # For the current month
    month_year = db.Column(db.String(7))  # "2026-02" format

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = db.relationship('User', backref='budget_categories')
    plan = db.relationship('BudgetPlan', backref='categories')
