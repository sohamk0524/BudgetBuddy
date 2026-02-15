"""
Unit tests for db_models.py - Database models and ORM.
"""

import pytest
import json
from werkzeug.security import generate_password_hash, check_password_hash
from db_models import db, User, FinancialProfile, BudgetPlan


@pytest.mark.unit
class TestUserModel:
    """Tests for User database model."""

    def test_create_user(self, app):
        """Test creating a user."""
        with app.app_context():
            user = User(
                email="newuser@example.com",
                password_hash=generate_password_hash("mypassword")
            )
            db.session.add(user)
            db.session.commit()

            assert user.id is not None
            assert user.email == "newuser@example.com"
            assert user.password_hash is not None

    def test_user_email_unique(self, app):
        """Test that email must be unique."""
        with app.app_context():
            user1 = User(
                email="duplicate@example.com",
                password_hash=generate_password_hash("pass1")
            )
            db.session.add(user1)
            db.session.commit()

            user2 = User(
                email="duplicate@example.com",
                password_hash=generate_password_hash("pass2")
            )
            db.session.add(user2)

            with pytest.raises(Exception):
                db.session.commit()

    def test_user_password_hash(self, app):
        """Test password hashing and verification."""
        with app.app_context():
            password = "secure_password_123"
            user = User(
                email="hashtest@example.com",
                password_hash=generate_password_hash(password)
            )
            db.session.add(user)
            db.session.commit()

            # Correct password should verify
            assert check_password_hash(user.password_hash, password)

            # Wrong password should not verify
            assert not check_password_hash(user.password_hash, "wrong_password")

    def test_user_profile_relationship(self, app):
        """Test the relationship between User and FinancialProfile."""
        with app.app_context():
            user = User(
                email="profile_test@example.com",
                password_hash=generate_password_hash("password")
            )
            db.session.add(user)
            db.session.flush()

            profile = FinancialProfile(
                user_id=user.id,
                is_student=True,
                budgeting_goal="stability",
                strictness_level="moderate"
            )
            db.session.add(profile)
            db.session.commit()

            # Test relationship
            assert user.profile is not None
            assert user.profile.is_student is True
            assert profile.user.email == "profile_test@example.com"


@pytest.mark.unit
class TestFinancialProfileModel:
    """Tests for FinancialProfile database model."""

    def test_create_profile(self, app, sample_user):
        """Test creating a financial profile."""
        with app.app_context():
            profile = FinancialProfile(
                user_id=sample_user,
                is_student=True,
                budgeting_goal="save_purchase",
                strictness_level="strict",
                savings_goal_name="Vacation",
                savings_goal_target=5000.0,
                housing_situation="own",
                debt_types=json.dumps(["car_loan"])
            )
            db.session.add(profile)
            db.session.commit()

            assert profile.id is not None
            assert profile.is_student is True
            assert profile.budgeting_goal == "save_purchase"
            assert profile.strictness_level == "strict"

    def test_profile_defaults(self, app, sample_user):
        """Test default values for profile fields."""
        with app.app_context():
            profile = FinancialProfile(user_id=sample_user)
            db.session.add(profile)
            db.session.commit()

            assert profile.is_student is False
            assert profile.fixed_expenses == 0.0
            assert profile.savings_goal_target == 0.0

    def test_profile_debt_types_json(self, app, sample_user):
        """Test storing and retrieving debt types as JSON."""
        with app.app_context():
            debt_list = ["student_loans", "credit_cards", "medical"]
            profile = FinancialProfile(
                user_id=sample_user,
                debt_types=json.dumps(debt_list)
            )
            db.session.add(profile)
            db.session.commit()

            # Retrieve and parse
            retrieved_profile = FinancialProfile.query.get(profile.id)
            parsed_debts = json.loads(retrieved_profile.debt_types)

            assert parsed_debts == debt_list
            assert len(parsed_debts) == 3

    def test_update_profile(self, app, sample_user_with_profile):
        """Test updating an existing profile."""
        with app.app_context():
            user = User.query.get(sample_user_with_profile)
            profile = user.profile

            # Update values
            profile.strictness_level = "strict"
            profile.savings_goal_name = "New Car"
            db.session.commit()

            # Verify updates
            updated_profile = user.profile
            assert updated_profile.strictness_level == "strict"
            assert updated_profile.savings_goal_name == "New Car"


@pytest.mark.unit
class TestBudgetPlanModel:
    """Tests for BudgetPlan database model."""

    def test_create_budget_plan(self, app, sample_user, sample_plan_data):
        """Test creating a budget plan."""
        with app.app_context():
            plan = BudgetPlan(
                user_id=sample_user,
                plan_json=json.dumps(sample_plan_data),
                month_year="2024-01"
            )
            db.session.add(plan)
            db.session.commit()

            assert plan.id is not None
            assert plan.user_id == sample_user
            assert plan.month_year == "2024-01"
            assert plan.created_at is not None

    def test_plan_json_storage(self, app, sample_user, sample_plan_data):
        """Test storing and retrieving plan JSON."""
        with app.app_context():
            plan = BudgetPlan(
                user_id=sample_user,
                plan_json=json.dumps(sample_plan_data),
                month_year="2024-02"
            )
            db.session.add(plan)
            db.session.commit()

            # Retrieve and parse
            retrieved_plan = BudgetPlan.query.get(plan.id)
            parsed_plan = json.loads(retrieved_plan.plan_json)

            assert parsed_plan["safeToSpend"] == 1000.0
            assert parsed_plan["totalIncome"] == 5000.0
            assert len(parsed_plan["categoryAllocations"]) == 1

    def test_user_budget_plans_relationship(self, app, sample_user, sample_plan_data):
        """Test the relationship between User and BudgetPlan."""
        with app.app_context():
            # Create multiple plans for the same user
            plan1 = BudgetPlan(
                user_id=sample_user,
                plan_json=json.dumps(sample_plan_data),
                month_year="2024-01"
            )
            plan2 = BudgetPlan(
                user_id=sample_user,
                plan_json=json.dumps(sample_plan_data),
                month_year="2024-02"
            )
            db.session.add(plan1)
            db.session.add(plan2)
            db.session.commit()

            # Test relationship
            user = User.query.get(sample_user)
            assert len(user.budget_plans) == 2

    def test_query_most_recent_plan(self, app, sample_user, sample_plan_data):
        """Test querying the most recent plan for a user."""
        with app.app_context():
            from datetime import datetime, timedelta

            # Create first plan with older timestamp
            plan1 = BudgetPlan(
                user_id=sample_user,
                plan_json=json.dumps(sample_plan_data),
                month_year="2024-01"
            )
            db.session.add(plan1)
            db.session.flush()
            # Manually set older timestamp
            plan1.created_at = datetime.now() - timedelta(hours=1)
            db.session.commit()

            # Create second plan with newer timestamp
            plan2 = BudgetPlan(
                user_id=sample_user,
                plan_json=json.dumps(sample_plan_data),
                month_year="2024-02"
            )
            db.session.add(plan2)
            db.session.commit()

            # Query most recent
            most_recent = BudgetPlan.query.filter_by(
                user_id=sample_user
            ).order_by(BudgetPlan.created_at.desc()).first()

            assert most_recent.month_year == "2024-02"
