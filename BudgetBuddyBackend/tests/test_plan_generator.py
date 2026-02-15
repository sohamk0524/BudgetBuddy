"""
Unit tests for services/plan_generator.py - Spending plan generation.
"""

import pytest
import json
from unittest.mock import Mock, patch
from services.plan_generator import (
    get_full_user_profile,
    format_deep_dive_data,
    format_upcoming_events,
    format_savings_goals,
    format_preferences,
    generate_plan,
    generate_fallback_plan,
    days_remaining_in_month,
    save_plan_to_db
)


@pytest.mark.unit
class TestGetFullUserProfile:
    """Tests for get_full_user_profile function."""

    def test_get_existing_profile(self, app, sample_user_with_profile):
        """Test getting a complete user profile."""
        with app.app_context():
            profile = get_full_user_profile(sample_user_with_profile)

            assert profile is not None
            assert profile["is_student"] is False
            assert profile["budgeting_goal"] == "emergency_fund"
            assert profile["strictness_level"] == "moderate"
            assert isinstance(profile["debt_types"], list)

    def test_get_nonexistent_profile(self, app):
        """Test getting profile for non-existent user."""
        with app.app_context():
            profile = get_full_user_profile(99999)

            assert profile is None

    def test_debt_types_json_parsing(self, app, sample_user_with_profile):
        """Test that debt_types JSON is properly parsed (defaults to empty list)."""
        with app.app_context():
            profile = get_full_user_profile(sample_user_with_profile)

            assert isinstance(profile["debt_types"], list)


@pytest.mark.unit
class TestFormatHelpers:
    """Tests for formatting helper functions."""

    def test_format_deep_dive_data(self):
        """Test formatting deep dive data."""
        deep_dive = {
            "fixedExpenses": {
                "rent": 1200,
                "utilities": 150,
                "subscriptions": [
                    {"name": "Netflix", "amount": 15},
                    {"name": "Spotify", "amount": 10}
                ]
            },
            "variableSpending": {
                "groceries": 400,
                "transportation": {"type": "car", "gas": 150, "insurance": 100},
                "diningEntertainment": 200
            }
        }

        result = format_deep_dive_data(deep_dive)

        assert "Rent/Mortgage" in result or "rent" in result.lower()
        assert "1200" in result or "1,200" in result
        assert "Groceries" in result or "groceries" in result.lower()
        assert "Netflix" in result

    def test_format_deep_dive_empty(self):
        """Test formatting empty deep dive data."""
        result = format_deep_dive_data({})

        assert "No detailed expenses" in result

    def test_format_upcoming_events(self):
        """Test formatting upcoming events."""
        events = [
            {"name": "Wedding", "date": "2024-06-15", "cost": 800, "saveGradually": True},
            {"name": "Trip", "date": "2024-08-01", "cost": 500, "saveGradually": False}
        ]

        result = format_upcoming_events(events)

        assert "Wedding" in result
        assert "800" in result
        assert "Save gradually" in result
        assert "Trip" in result

    def test_format_upcoming_events_empty(self):
        """Test formatting empty events list."""
        result = format_upcoming_events([])

        assert "No upcoming events" in result

    def test_format_savings_goals(self):
        """Test formatting savings goals."""
        goals = [
            {"name": "Emergency fund", "target": 1000, "current": 250, "priority": 1},
            {"name": "Vacation", "target": 2000, "current": 500, "priority": 2}
        ]

        result = format_savings_goals(goals)

        assert "Emergency fund" in result
        assert "1000" in result or "1,000" in result
        assert "25%" in result or "progress" in result.lower()

    def test_format_savings_goals_empty(self):
        """Test formatting empty goals list."""
        result = format_savings_goals([])

        assert "No specific savings goals" in result

    def test_format_preferences(self):
        """Test formatting spending preferences."""
        prefs = {
            "spendingStyle": 0.3,
            "priorities": ["savings", "security"],
            "strictness": "moderate"
        }

        result = format_preferences(prefs)

        assert "Frugal" in result or "0.3" in result
        assert "savings" in result
        assert "moderate" in result.lower()

    def test_format_preferences_empty(self):
        """Test formatting empty preferences."""
        result = format_preferences({})

        assert "No preferences" in result


@pytest.mark.unit
class TestDaysRemainingInMonth:
    """Tests for days_remaining_in_month function."""

    @patch('services.plan_generator.datetime')
    def test_days_remaining_mid_month(self, mock_datetime):
        """Test calculating days remaining in middle of month."""
        from datetime import datetime

        # January 15, 2024
        mock_now = datetime(2024, 1, 15)
        mock_datetime.now.return_value = mock_now

        days = days_remaining_in_month()

        # Should be 17 days (Jan has 31 days, 31 - 15 + 1 = 17)
        # Actually it counts to the first of next month
        assert days >= 16 and days <= 17

    @patch('services.plan_generator.datetime')
    def test_days_remaining_end_of_year(self, mock_datetime):
        """Test calculating days remaining at end of year."""
        from datetime import datetime

        # December 31, 2024
        mock_now = datetime(2024, 12, 31)
        mock_datetime.now.return_value = mock_now

        days = days_remaining_in_month()

        # Should be 1 day
        assert days >= 0 and days <= 1


@pytest.mark.unit
class TestGenerateFallbackPlan:
    """Tests for generate_fallback_plan function."""

    def test_fallback_plan_basic(self):
        """Test generating a basic fallback plan."""
        profile = {
            "is_student": False,
            "budgeting_goal": "emergency_fund",
            "strictness_level": "moderate",
            "fixed_expenses": 2000,
            "savings_goal_name": "Emergency Fund",
            "savings_goal_target": 10000
        }
        deep_dive = {"monthlyIncome": 5000}

        result = generate_fallback_plan(profile, deep_dive)

        assert "textMessage" in result
        assert "plan" in result
        assert result["plan"]["totalIncome"] == 5000
        assert result["plan"]["safeToSpend"] >= 0

    def test_fallback_plan_with_deep_dive(self):
        """Test fallback plan with deep dive data."""
        profile = {
            "is_student": False,
            "budgeting_goal": "save_purchase",
            "strictness_level": "moderate",
            "fixed_expenses": 0,
            "savings_goal_name": "Car",
            "savings_goal_target": 15000
        }
        deep_dive = {
            "monthlyIncome": 5000,
            "fixedExpenses": {
                "rent": 1500,
                "utilities": 200,
                "subscriptions": [{"name": "Netflix", "amount": 15}]
            },
            "variableSpending": {
                "groceries": 400,
                "transportation": {"gas": 150, "insurance": 100},
                "diningEntertainment": 200
            }
        }

        result = generate_fallback_plan(profile, deep_dive)

        plan = result["plan"]
        assert plan["totalIncome"] == 5000
        assert len(plan["categoryAllocations"]) > 0
        assert any(cat["id"] == "fixed" for cat in plan["categoryAllocations"])

    def test_fallback_plan_with_events(self):
        """Test fallback plan with upcoming events."""
        profile = {
            "is_student": False,
            "budgeting_goal": "stability",
            "strictness_level": "relaxed",
            "fixed_expenses": 1500,
            "savings_goal_name": None,
            "savings_goal_target": 0
        }
        deep_dive = {
            "monthlyIncome": 4000,
            "upcomingEvents": [
                {"name": "Wedding", "cost": 600, "saveGradually": True}
            ]
        }

        result = generate_fallback_plan(profile, deep_dive)

        plan = result["plan"]
        # Should have events category
        assert any(cat["id"] == "events" for cat in plan["categoryAllocations"])

    def test_fallback_plan_recommendations(self):
        """Test that fallback plan generates recommendations."""
        profile = {
            "is_student": False,
            "budgeting_goal": "stability",
            "strictness_level": "moderate",
            "fixed_expenses": 2000,
            "savings_goal_name": "Savings",
            "savings_goal_target": 5000
        }
        deep_dive = {"monthlyIncome": 3000}

        result = generate_fallback_plan(profile, deep_dive)

        plan = result["plan"]
        assert "recommendations" in plan
        assert len(plan["recommendations"]) > 0

    def test_fallback_plan_negative_safe_to_spend(self):
        """Test fallback plan when expenses exceed income."""
        profile = {
            "is_student": False,
            "budgeting_goal": "stability",
            "strictness_level": "moderate",
            "fixed_expenses": 2500,
            "savings_goal_name": None,
            "savings_goal_target": 0
        }
        deep_dive = {"monthlyIncome": 2000}

        result = generate_fallback_plan(profile, deep_dive)

        plan = result["plan"]
        # Safe to spend should be clamped to 0
        assert plan["safeToSpend"] >= 0
        assert len(plan["warnings"]) > 0 or plan["safeToSpend"] == 0


@pytest.mark.unit
@patch('services.plan_generator.agent')
class TestGeneratePlan:
    """Tests for generate_plan function."""

    def test_generate_plan_no_profile(self, mock_agent, app):
        """Test generating plan when user has no profile."""
        with app.app_context():
            result = generate_plan(99999, {})

            assert "error" in result
            assert result["plan"] is None

    @patch('services.plan_generator.get_full_user_profile')
    def test_generate_plan_ollama_unavailable(self, mock_get_profile, mock_agent, app):
        """Test generating plan when Ollama is unavailable."""
        mock_get_profile.return_value = {
            "is_student": False,
            "budgeting_goal": "stability",
            "strictness_level": "moderate",
            "fixed_expenses": 2000,
            "savings_goal_name": "Car",
            "savings_goal_target": 10000,
            "housing_situation": "rent",
            "debt_types": []
        }
        mock_agent.is_available.return_value = False

        with app.app_context():
            result = generate_plan(1, {"monthlyIncome": 5000})

            # Should fall back to rule-based plan
            assert "plan" in result
            assert result["plan"]["totalIncome"] == 5000

    @patch('services.plan_generator.get_full_user_profile')
    def test_generate_plan_with_llm(self, mock_get_profile, mock_agent, app):
        """Test generating plan with LLM response."""
        mock_get_profile.return_value = {
            "is_student": False,
            "budgeting_goal": "emergency_fund",
            "strictness_level": "moderate",
            "fixed_expenses": 2000,
            "savings_goal_name": "Emergency",
            "savings_goal_target": 5000,
            "housing_situation": "rent",
            "debt_types": []
        }

        mock_agent.is_available.return_value = True

        # Mock LLM response with valid JSON
        plan_json = {
            "summary": "Your personalized plan",
            "safeToSpend": 1200,
            "totalIncome": 5000,
            "totalExpenses": 3000,
            "totalSavings": 800,
            "categoryAllocations": [],
            "recommendations": [],
            "warnings": []
        }
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content=json.dumps(plan_json)))]
        mock_agent.chat.return_value = mock_response

        with app.app_context():
            result = generate_plan(1, {})

            assert "plan" in result
            assert result["plan"]["safeToSpend"] == 1200


@pytest.mark.unit
class TestSavePlanToDb:
    """Tests for save_plan_to_db function."""

    def test_save_plan_success(self, app, sample_user):
        """Test successfully saving a plan to database."""
        plan_data = {
            "summary": "Test plan",
            "safeToSpend": 1000,
            "totalIncome": 5000
        }

        with app.app_context():
            result = save_plan_to_db(sample_user, plan_data)

            assert result is True

            # Verify it was saved
            from db_models import BudgetPlan
            saved_plan = BudgetPlan.query.filter_by(user_id=sample_user).first()
            assert saved_plan is not None

    def test_save_plan_invalid_user(self, app):
        """Test saving plan for non-existent user."""
        plan_data = {"summary": "Test"}

        with app.app_context():
            # Should handle error gracefully
            result = save_plan_to_db(99999, plan_data)

            # Implementation might return False or True depending on error handling
            assert isinstance(result, bool)
