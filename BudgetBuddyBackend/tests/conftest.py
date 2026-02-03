"""
Pytest configuration and fixtures for BudgetBuddy tests.
"""

import pytest
import sys
import os

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app as flask_app
from db_models import db, User, FinancialProfile, BudgetPlan


@pytest.fixture
def app():
    """Create and configure a test Flask application."""
    flask_app.config.update({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        'SQLALCHEMY_TRACK_MODIFICATIONS': False
    })

    with flask_app.app_context():
        db.create_all()
        yield flask_app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """Create a test client for the Flask application."""
    return app.test_client()


@pytest.fixture
def runner(app):
    """Create a test CLI runner."""
    return app.test_cli_runner()


@pytest.fixture
def sample_user(app):
    """Create a sample user in the test database."""
    from werkzeug.security import generate_password_hash

    with app.app_context():
        user = User(
            email="test@example.com",
            password_hash=generate_password_hash("password123")
        )
        db.session.add(user)
        db.session.commit()

        # Return user ID since the object becomes detached after commit
        user_id = user.id

    return user_id


@pytest.fixture
def sample_user_with_profile(app):
    """Create a sample user with a complete financial profile."""
    from werkzeug.security import generate_password_hash
    import json

    with app.app_context():
        user = User(
            email="profile@example.com",
            password_hash=generate_password_hash("password123")
        )
        db.session.add(user)
        db.session.flush()

        profile = FinancialProfile(
            user_id=user.id,
            monthly_income=5000.0,
            fixed_expenses=2000.0,
            savings_goal_name="Emergency Fund",
            savings_goal_target=10000.0,
            income_frequency="monthly",
            housing_situation="rent",
            debt_types=json.dumps(["student_loans", "credit_cards"]),
            financial_personality="balanced",
            primary_goal="emergency_fund"
        )
        db.session.add(profile)
        db.session.commit()

        user_id = user.id

    return user_id


@pytest.fixture
def sample_plan_data():
    """Sample spending plan data for testing."""
    return {
        "summary": "Test spending plan",
        "safeToSpend": 1000.0,
        "totalIncome": 5000.0,
        "totalExpenses": 3000.0,
        "totalSavings": 1000.0,
        "daysRemaining": 15,
        "budgetUsedPercent": 0.4,
        "categoryAllocations": [
            {
                "id": "fixed",
                "name": "Fixed Essentials",
                "amount": 2000.0,
                "color": "#FF6B6B",
                "items": [{"name": "Rent", "amount": 1500.0}]
            }
        ],
        "recommendations": [
            {
                "category": "groceries",
                "title": "Save on groceries",
                "description": "Try meal planning",
                "potentialSavings": 100.0
            }
        ],
        "warnings": []
    }


@pytest.fixture
def mock_llm_response():
    """Mock LLM response for testing."""
    class MockChoice:
        def __init__(self, content):
            self.message = type('obj', (object,), {
                'content': content,
                'tool_calls': None
            })()

    class MockResponse:
        def __init__(self, content):
            self.choices = [MockChoice(content)]

    return MockResponse


@pytest.fixture
def sample_csv_content():
    """Sample CSV bank statement content."""
    return b"""Date,Description,Amount,Category
2024-01-01,Salary,5000.00,Income
2024-01-02,Rent,-1500.00,Housing
2024-01-03,Grocery Store,-120.50,Food
2024-01-04,Gas Station,-45.00,Transportation
2024-01-05,Restaurant,-35.00,Dining
"""
