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
