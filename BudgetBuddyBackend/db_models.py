"""
Database models for BudgetBuddy authentication and user profiles.
Uses SQLAlchemy for ORM with SQLite database.
"""

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class User(db.Model):
    """User account for authentication."""
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    profile = db.relationship('FinancialProfile', backref='user', uselist=False)


class FinancialProfile(db.Model):
    """User's financial profile from onboarding."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    monthly_income = db.Column(db.Float, default=0.0)
    fixed_expenses = db.Column(db.Float, default=0.0)
    savings_goal_name = db.Column(db.String(100))
    savings_goal_target = db.Column(db.Float, default=0.0)

    # New fields for expanded onboarding
    income_frequency = db.Column(db.String(20))  # "biweekly", "monthly", "irregular"
    housing_situation = db.Column(db.String(20))  # "rent", "own", "family"
    debt_types = db.Column(db.String(200))  # JSON array: ["student_loans", "credit_cards", "car"]
    financial_personality = db.Column(db.String(30))  # "aggressive_saver", "balanced", "paycheck_to_paycheck"
    primary_goal = db.Column(db.String(30))  # "emergency_fund", "pay_debt", "save_purchase", "stability"


class BudgetPlan(db.Model):
    """Generated spending plan for a user."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    plan_json = db.Column(db.Text, nullable=False)  # Full plan as JSON
    created_at = db.Column(db.DateTime, default=db.func.now())
    month_year = db.Column(db.String(7))  # "2026-02" format

    user = db.relationship('User', backref='budget_plans')
