"""
Database models for BudgetBuddy authentication and user profiles.
Uses SQLAlchemy for ORM with SQLite database.
"""

from datetime import datetime, timedelta
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class User(db.Model):
    """User account for SMS-based authentication."""
    id = db.Column(db.Integer, primary_key=True)
    phone_number = db.Column(db.String(20), unique=True, nullable=False)  # E.164 format
    name = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    profile = db.relationship('FinancialProfile', backref='user', uselist=False, cascade='all, delete-orphan')
    statement = db.relationship('SavedStatement', backref='user', uselist=False, cascade='all, delete-orphan')
    budget_plans = db.relationship('BudgetPlan', backref='user_ref', cascade='all, delete-orphan')


class OTPCode(db.Model):
    """One-time password codes for SMS verification."""
    id = db.Column(db.Integer, primary_key=True)
    phone_number = db.Column(db.String(20), nullable=False, index=True)
    code = db.Column(db.String(6), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)
    verified = db.Column(db.Boolean, default=False)


class UserCategoryPreference(db.Model):
    """User's pinned category preferences for the homepage."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    category_name = db.Column(db.String(100), nullable=False)
    display_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='category_preferences')


class FinancialProfile(db.Model):
    """User's financial profile from onboarding (4-Question Protocol)."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    # 4-Question Protocol fields
    is_student = db.Column(db.Boolean, default=False)  # "Are you currently a student?"
    budgeting_goal = db.Column(db.String(30))  # "emergency_fund", "pay_debt", "save_purchase", "stability"
    strictness_level = db.Column(db.String(20))  # "relaxed", "moderate", "strict"

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


class PlaidItem(db.Model):
    """
    Represents a user's linked bank connection via Plaid.
    Each PlaidItem corresponds to one institution connection.
    """
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    # Plaid identifiers
    item_id = db.Column(db.String(100), unique=True, nullable=False)
    access_token_encrypted = db.Column(db.LargeBinary, nullable=False)

    # Transaction sync cursor for incremental updates
    transactions_cursor = db.Column(db.String(500), nullable=True)

    # Institution info
    institution_id = db.Column(db.String(50), nullable=True)
    institution_name = db.Column(db.String(200), nullable=True)

    # Status: active, error, pending_expiration
    status = db.Column(db.String(30), default='active')

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = db.relationship('User', backref='plaid_items')
    accounts = db.relationship('PlaidAccount', backref='plaid_item', cascade='all, delete-orphan')


class PlaidAccount(db.Model):
    """
    Represents an individual bank account within a PlaidItem.
    A single bank connection can have multiple accounts (checking, savings, etc.)
    """
    id = db.Column(db.Integer, primary_key=True)
    plaid_item_id = db.Column(db.Integer, db.ForeignKey('plaid_item.id'), nullable=False)

    # Plaid identifiers
    account_id = db.Column(db.String(100), unique=True, nullable=False)

    # Account info
    name = db.Column(db.String(200), nullable=False)
    official_name = db.Column(db.String(200), nullable=True)
    account_type = db.Column(db.String(50), nullable=True)  # depository, credit, loan, etc.
    account_subtype = db.Column(db.String(50), nullable=True)  # checking, savings, credit card, etc.

    # Balances
    balance_available = db.Column(db.Float, nullable=True)
    balance_current = db.Column(db.Float, nullable=True)
    balance_limit = db.Column(db.Float, nullable=True)  # For credit accounts

    # Last 4 digits of account number
    mask = db.Column(db.String(10), nullable=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    transactions = db.relationship('Transaction', backref='plaid_account', cascade='all, delete-orphan')


class Transaction(db.Model):
    """
    Represents an individual transaction from Plaid.
    Stores both pending and posted transactions.
    """
    id = db.Column(db.Integer, primary_key=True)
    plaid_account_id = db.Column(db.Integer, db.ForeignKey('plaid_account.id'), nullable=False)

    # Plaid identifiers
    transaction_id = db.Column(db.String(100), unique=True, nullable=False)

    # Transaction details
    amount = db.Column(db.Float, nullable=False)  # Positive = money out, negative = money in
    date = db.Column(db.Date, nullable=False)
    authorized_date = db.Column(db.Date, nullable=True)
    name = db.Column(db.String(500), nullable=False)  # Transaction description
    merchant_name = db.Column(db.String(200), nullable=True)

    # Category info (Plaid's detailed categorization)
    category_primary = db.Column(db.String(100), nullable=True)
    category_detailed = db.Column(db.String(100), nullable=True)
    category_confidence = db.Column(db.String(20), nullable=True)  # VERY_HIGH, HIGH, MEDIUM, LOW

    # Transaction status
    pending = db.Column(db.Boolean, default=False)
    payment_channel = db.Column(db.String(50), nullable=True)  # online, in store, other

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
