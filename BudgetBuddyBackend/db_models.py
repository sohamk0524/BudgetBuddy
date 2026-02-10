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
