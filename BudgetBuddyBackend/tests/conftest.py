"""
Pytest configuration and fixtures for BudgetBuddy tests.
"""

import pytest
import sys
import os
from unittest.mock import patch, MagicMock

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app as flask_app
from db_models import db, User, FinancialProfile, BudgetPlan, PlaidItem, PlaidAccount, Transaction


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


# =============================================================================
# Plaid Integration Fixtures
# =============================================================================

@pytest.fixture
def sample_user_for_plaid(app):
    """Create a sample user for Plaid integration tests."""
    from werkzeug.security import generate_password_hash

    with app.app_context():
        user = User(
            email="plaid_test@example.com",
            password_hash=generate_password_hash("password123")
        )
        db.session.add(user)
        db.session.commit()
        user_id = user.id

    return user_id


@pytest.fixture
def mock_plaid_exchange(app):
    """Mock Plaid token exchange and related API calls."""
    # Set up environment variables for encryption
    with patch.dict('os.environ', {
        'FERNET_KEY': 'VGhpcyBpcyBhIDMyIGJ5dGUga2V5IGZvciB0ZXN0cyE=',
        'PLAID_CLIENT_ID': 'test_client_id',
        'PLAID_SECRET': 'test_secret',
        'PLAID_ENV': 'sandbox'
    }):
        with patch('services.plaid_service.get_plaid_client') as mock_client:
            # Mock token exchange
            mock_exchange_response = MagicMock()
            mock_exchange_response.access_token = "access-sandbox-test-token"
            mock_exchange_response.item_id = "test-item-id"
            mock_client.return_value.item_public_token_exchange.return_value = mock_exchange_response

            # Mock accounts get
            mock_account = MagicMock()
            mock_account.account_id = "test-account-id"
            mock_account.name = "Test Checking"
            mock_account.official_name = "Test Official Checking"
            mock_account.type = MagicMock(value="depository")
            mock_account.subtype = MagicMock(value="checking")
            mock_account.mask = "1234"
            mock_account.balances.available = 1000.0
            mock_account.balances.current = 1200.0
            mock_account.balances.limit = None

            mock_accounts_response = MagicMock()
            mock_accounts_response.accounts = [mock_account]
            mock_accounts_response.item.item_id = "test-item-id"
            mock_accounts_response.item.institution_id = "ins_109508"
            mock_accounts_response.request_id = "test-request-id"
            mock_client.return_value.accounts_get.return_value = mock_accounts_response

            # Mock transactions get (historical)
            mock_txn = MagicMock()
            mock_txn.transaction_id = "test-txn-1"
            mock_txn.account_id = "test-account-id"
            mock_txn.amount = 50.0
            mock_txn.date = MagicMock()
            mock_txn.date.isoformat.return_value = "2026-01-15"
            mock_txn.authorized_date = None
            mock_txn.name = "Coffee Shop"
            mock_txn.merchant_name = "Starbucks"
            mock_txn.personal_finance_category = MagicMock()
            mock_txn.personal_finance_category.primary = "FOOD_AND_DRINK"
            mock_txn.personal_finance_category.detailed = "COFFEE_SHOPS"
            mock_txn.personal_finance_category.confidence_level = "HIGH"
            mock_txn.pending = False
            mock_txn.payment_channel = MagicMock(value="in_store")

            mock_txns_response = MagicMock()
            mock_txns_response.transactions = [mock_txn]
            mock_txns_response.total_transactions = 1
            mock_client.return_value.transactions_get.return_value = mock_txns_response

            yield mock_client


@pytest.fixture
def sample_plaid_item(app, sample_user_for_plaid):
    """Create a sample PlaidItem with accounts and transactions."""
    with app.app_context():
        # Create encrypted token (mock)
        encrypted_token = b'mock_encrypted_token'

        plaid_item = PlaidItem(
            user_id=sample_user_for_plaid,
            item_id="test-item-id",
            access_token_encrypted=encrypted_token,
            institution_id="ins_109508",
            institution_name="First Platypus Bank",
            status="active"
        )
        db.session.add(plaid_item)
        db.session.flush()

        account = PlaidAccount(
            plaid_item_id=plaid_item.id,
            account_id="test-account-id",
            name="Test Checking",
            account_type="depository",
            account_subtype="checking",
            balance_available=1000.0,
            balance_current=1200.0,
            mask="1234"
        )
        db.session.add(account)
        db.session.flush()

        from datetime import date
        transaction = Transaction(
            plaid_account_id=account.id,
            transaction_id="test-txn-1",
            amount=50.0,
            date=date(2026, 1, 15),
            name="Coffee Shop",
            merchant_name="Starbucks",
            category_primary="FOOD_AND_DRINK",
            pending=False
        )
        db.session.add(transaction)
        db.session.commit()

        item_id = plaid_item.id

    return item_id
