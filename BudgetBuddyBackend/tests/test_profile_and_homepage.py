"""
Tests for user profile endpoints, top expenses, category preferences,
nudges endpoint, and name support in auth/onboarding.
"""

import pytest
import json
from datetime import date, timedelta
from db_models import db, User, UserCategoryPreference


# =============================================================================
# Auth Name Support
# =============================================================================

@pytest.mark.integration
class TestAuthNameSupport:
    """Tests for name field in register, login, and onboarding."""

    def test_register_with_name(self, client):
        """Test registering a user with a name."""
        response = client.post(
            "/register",
            json={"email": "named@test.com", "password": "pass123", "name": "Alex"}
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["status"] == "success"
        assert "token" in data

    def test_register_without_name(self, client):
        """Test registering a user without a name still works."""
        response = client.post(
            "/register",
            json={"email": "noname@test.com", "password": "pass123"}
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["status"] == "success"

    def test_login_returns_name(self, client, sample_user_with_name):
        """Test that login response includes the user's name."""
        response = client.post(
            "/login",
            json={"email": "named@example.com", "password": "password123"}
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert "name" in data
        assert data["name"] == "Test User"

    def test_login_returns_null_name_when_unset(self, client, sample_user):
        """Test that login returns null name when user has no name."""
        response = client.post(
            "/login",
            json={"email": "test@example.com", "password": "password123"}
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert "name" in data
        assert data["name"] is None

    def test_onboarding_with_name(self, client, sample_user):
        """Test onboarding saves name."""
        response = client.post(
            "/onboarding",
            json={
                "userId": sample_user,
                "name": "Onboarded User",
                "age": 25,
                "occupation": "student",
                "income": 2000.0,
                "incomeFrequency": "monthly",
                "financialPersonality": "balanced",
                "primaryGoal": "stability"
            }
        )

        assert response.status_code == 200

        # Verify name was saved via profile endpoint
        response = client.get(f"/user/profile/{sample_user}")
        data = json.loads(response.data)
        assert data["name"] == "Onboarded User"

    def test_onboarding_without_name(self, client, sample_user):
        """Test onboarding works without name field."""
        response = client.post(
            "/onboarding",
            json={
                "userId": sample_user,
                "age": 22,
                "occupation": "student",
                "income": 1500.0
            }
        )

        assert response.status_code == 200


# =============================================================================
# User Profile Endpoints
# =============================================================================

@pytest.mark.integration
class TestUserProfileEndpoints:
    """Tests for GET/PUT /user/profile/<user_id>."""

    def test_get_profile_with_data(self, client, sample_user_with_name):
        """Test getting a fully populated profile."""
        response = client.get(f"/user/profile/{sample_user_with_name}")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["name"] == "Test User"
        assert data["email"] == "named@example.com"
        assert data["profile"] is not None
        assert data["profile"]["age"] == 25
        assert data["profile"]["occupation"] == "employed"
        assert data["profile"]["monthlyIncome"] == 5000.0
        assert data["profile"]["incomeFrequency"] == "monthly"
        assert data["profile"]["financialPersonality"] == "balanced"
        assert data["profile"]["primaryGoal"] == "emergency_fund"
        assert isinstance(data["plaidItems"], list)

    def test_get_profile_no_profile(self, client, sample_user):
        """Test getting profile for user without financial profile."""
        response = client.get(f"/user/profile/{sample_user}")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["email"] == "test@example.com"
        assert data["profile"] is None

    def test_get_profile_nonexistent_user(self, client):
        """Test getting profile for non-existent user."""
        response = client.get("/user/profile/99999")

        assert response.status_code == 404

    def test_update_profile_name(self, client, sample_user_with_name):
        """Test updating just the name."""
        response = client.put(
            f"/user/profile/{sample_user_with_name}",
            json={"name": "New Name"}
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["status"] == "success"

        # Verify
        response = client.get(f"/user/profile/{sample_user_with_name}")
        data = json.loads(response.data)
        assert data["name"] == "New Name"

    def test_update_profile_financial_fields(self, client, sample_user_with_name):
        """Test updating financial profile fields."""
        response = client.put(
            f"/user/profile/{sample_user_with_name}",
            json={
                "age": 30,
                "occupation": "self_employed",
                "monthlyIncome": 8000.0,
                "primaryGoal": "pay_debt"
            }
        )

        assert response.status_code == 200

        # Verify
        response = client.get(f"/user/profile/{sample_user_with_name}")
        data = json.loads(response.data)
        assert data["profile"]["age"] == 30
        assert data["profile"]["occupation"] == "self_employed"
        assert data["profile"]["monthlyIncome"] == 8000.0
        assert data["profile"]["primaryGoal"] == "pay_debt"
        # Unchanged fields preserved
        assert data["profile"]["incomeFrequency"] == "monthly"

    def test_update_profile_partial(self, client, sample_user_with_name):
        """Test partial update only changes specified fields."""
        response = client.put(
            f"/user/profile/{sample_user_with_name}",
            json={"financialPersonality": "aggressive_saver"}
        )

        assert response.status_code == 200

        response = client.get(f"/user/profile/{sample_user_with_name}")
        data = json.loads(response.data)
        assert data["profile"]["financialPersonality"] == "aggressive_saver"
        assert data["profile"]["monthlyIncome"] == 5000.0  # Unchanged
        assert data["name"] == "Test User"  # Unchanged

    def test_update_profile_nonexistent_user(self, client):
        """Test updating profile for non-existent user."""
        response = client.put(
            "/user/profile/99999",
            json={"name": "Ghost"}
        )

        assert response.status_code == 404

    def test_update_profile_no_json(self, client, sample_user_with_name):
        """Test update with no JSON body."""
        response = client.put(
            f"/user/profile/{sample_user_with_name}",
            data="not json",
            content_type="application/json"
        )

        assert response.status_code == 400

    def test_get_profile_includes_plaid_items(self, client, sample_plaid_item, sample_user_for_plaid):
        """Test that profile includes linked Plaid accounts."""
        response = client.get(f"/user/profile/{sample_user_for_plaid}")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data["plaidItems"]) == 1
        assert data["plaidItems"][0]["institutionName"] == "First Platypus Bank"
        assert data["plaidItems"][0]["status"] == "active"
        assert len(data["plaidItems"][0]["accounts"]) == 1


# =============================================================================
# Top Expenses Endpoint
# =============================================================================

@pytest.mark.integration
class TestTopExpensesEndpoint:
    """Tests for GET /user/top-expenses/<user_id>."""

    def test_top_expenses_with_plaid(self, client, sample_user_with_plaid_and_plan):
        """Test top expenses from Plaid transactions."""
        response = client.get(f"/user/top-expenses/{sample_user_with_plaid_and_plan}")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["source"] == "plaid"
        assert isinstance(data["topExpenses"], list)
        assert len(data["topExpenses"]) > 0
        assert data["totalSpending"] > 0
        assert data["period"] == 30

        # Verify structure of expense entries
        expense = data["topExpenses"][0]
        assert "category" in expense
        assert "amount" in expense
        assert "transactionCount" in expense

        # FOOD_AND_DRINK should be the highest
        assert data["topExpenses"][0]["category"] == "FOOD_AND_DRINK"
        assert data["topExpenses"][0]["amount"] == 450.0

    def test_top_expenses_no_data(self, client, sample_user):
        """Test top expenses with no Plaid data and no statement."""
        response = client.get(f"/user/top-expenses/{sample_user}")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["source"] == "none"
        assert data["topExpenses"] == []
        assert data["totalSpending"] == 0

    def test_top_expenses_custom_days(self, client, sample_user_with_plaid_and_plan):
        """Test top expenses with custom days parameter."""
        response = client.get(f"/user/top-expenses/{sample_user_with_plaid_and_plan}?days=7")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["period"] == 7

    def test_top_expenses_nonexistent_user(self, client):
        """Test top expenses for non-existent user."""
        response = client.get("/user/top-expenses/99999")

        assert response.status_code == 404


# =============================================================================
# Category Preferences Endpoints
# =============================================================================

@pytest.mark.integration
class TestCategoryPreferencesEndpoints:
    """Tests for GET/PUT /user/category-preferences/<user_id>."""

    def test_get_empty_preferences(self, client, sample_user):
        """Test getting preferences when none are set."""
        response = client.get(f"/user/category-preferences/{sample_user}")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["categories"] == []

    def test_set_preferences(self, client, sample_user):
        """Test setting category preferences."""
        response = client.put(
            f"/user/category-preferences/{sample_user}",
            json={"categories": ["FOOD_AND_DRINK", "TRANSPORTATION", "SHOPPING"]}
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["status"] == "success"

    def test_get_preferences_after_set(self, client, sample_user):
        """Test getting preferences after setting them."""
        # Set
        client.put(
            f"/user/category-preferences/{sample_user}",
            json={"categories": ["FOOD_AND_DRINK", "TRANSPORTATION"]}
        )

        # Get
        response = client.get(f"/user/category-preferences/{sample_user}")
        data = json.loads(response.data)
        assert len(data["categories"]) == 2
        assert data["categories"][0]["categoryName"] == "FOOD_AND_DRINK"
        assert data["categories"][0]["displayOrder"] == 0
        assert data["categories"][1]["categoryName"] == "TRANSPORTATION"
        assert data["categories"][1]["displayOrder"] == 1

    def test_replace_preferences(self, client, sample_user):
        """Test that setting preferences replaces existing ones."""
        # First set
        client.put(
            f"/user/category-preferences/{sample_user}",
            json={"categories": ["A", "B", "C"]}
        )

        # Replace
        client.put(
            f"/user/category-preferences/{sample_user}",
            json={"categories": ["X", "Y"]}
        )

        response = client.get(f"/user/category-preferences/{sample_user}")
        data = json.loads(response.data)
        assert len(data["categories"]) == 2
        assert data["categories"][0]["categoryName"] == "X"
        assert data["categories"][1]["categoryName"] == "Y"

    def test_set_preferences_missing_field(self, client, sample_user):
        """Test setting preferences without categories field."""
        response = client.put(
            f"/user/category-preferences/{sample_user}",
            json={"other": "data"}
        )

        assert response.status_code == 400

    def test_preferences_nonexistent_user(self, client):
        """Test preferences for non-existent user."""
        response = client.get("/user/category-preferences/99999")
        assert response.status_code == 404

        response = client.put(
            "/user/category-preferences/99999",
            json={"categories": ["A"]}
        )
        assert response.status_code == 404


# =============================================================================
# Nudges Endpoint
# =============================================================================

@pytest.mark.integration
class TestNudgesEndpoint:
    """Tests for GET /user/nudges/<user_id>."""

    def test_nudges_with_data(self, client, sample_user_with_plaid_and_plan):
        """Test nudges for user with Plaid data and a budget plan."""
        response = client.get(f"/user/nudges/{sample_user_with_plaid_and_plan}")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert "nudges" in data
        assert isinstance(data["nudges"], list)

        # Should have at least one nudge (FOOD_AND_DRINK is over budget)
        assert len(data["nudges"]) > 0

        # Verify nudge structure
        nudge = data["nudges"][0]
        assert "type" in nudge
        assert "title" in nudge
        assert "message" in nudge

    def test_nudges_spending_reduction(self, client, sample_user_with_plaid_and_plan):
        """Test that over-budget categories produce spending_reduction nudges."""
        response = client.get(f"/user/nudges/{sample_user_with_plaid_and_plan}")

        data = json.loads(response.data)
        types = [n["type"] for n in data["nudges"]]

        # FOOD_AND_DRINK: spent 450 on 300 budget = over budget
        assert "spending_reduction" in types

        # Find the food nudge
        food_nudges = [n for n in data["nudges"] if n.get("category") == "FOOD_AND_DRINK"]
        assert len(food_nudges) > 0
        assert food_nudges[0]["potentialSavings"] == 150.0

    def test_nudges_positive_reinforcement(self, client, sample_user_with_plaid_and_plan):
        """Test that under-budget categories produce positive nudges."""
        response = client.get(f"/user/nudges/{sample_user_with_plaid_and_plan}")

        data = json.loads(response.data)
        types = [n["type"] for n in data["nudges"]]

        # TRANSPORTATION: spent 80 on 200 budget = well under budget
        assert "positive_reinforcement" in types

    def test_nudges_no_data(self, client, sample_user):
        """Test nudges for user with no spending data or plan."""
        response = client.get(f"/user/nudges/{sample_user}")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["nudges"] == []

    def test_nudges_nonexistent_user(self, client):
        """Test nudges for non-existent user."""
        response = client.get("/user/nudges/99999")

        assert response.status_code == 404

    def test_nudges_goal_reminder(self, client, sample_user_with_plaid_and_plan):
        """Test that goal_reminder nudge appears when plan has savings."""
        response = client.get(f"/user/nudges/{sample_user_with_plaid_and_plan}")

        data = json.loads(response.data)
        types = [n["type"] for n in data["nudges"]]
        assert "goal_reminder" in types


# =============================================================================
# Nudge Generator Unit Tests
# =============================================================================

@pytest.mark.unit
class TestNudgeGenerator:
    """Unit tests for the nudge_generator service."""

    def test_compare_spending_over_budget(self, app):
        """Test nudge generation for over-budget categories."""
        from services.nudge_generator import _compare_spending

        actual = {"Food": 500.0}
        planned = {"Food": 300.0}

        nudges = _compare_spending(actual, planned)

        assert len(nudges) == 1
        assert nudges[0]["type"] == "spending_reduction"
        assert nudges[0]["category"] == "Food"
        assert nudges[0]["potentialSavings"] == 200.0

    def test_compare_spending_under_budget(self, app):
        """Test nudge generation for under-budget categories."""
        from services.nudge_generator import _compare_spending

        actual = {"Food": 100.0}
        planned = {"Food": 500.0}

        nudges = _compare_spending(actual, planned)

        assert len(nudges) == 1
        assert nudges[0]["type"] == "positive_reinforcement"

    def test_compare_spending_within_range(self, app):
        """Test no nudge for spending within normal range (70-110%)."""
        from services.nudge_generator import _compare_spending

        actual = {"Food": 280.0}
        planned = {"Food": 300.0}

        nudges = _compare_spending(actual, planned)

        assert len(nudges) == 0

    def test_compare_spending_case_insensitive(self, app):
        """Test category matching is case-insensitive."""
        from services.nudge_generator import _compare_spending

        actual = {"food_and_drink": 500.0}
        planned = {"FOOD_AND_DRINK": 300.0}

        nudges = _compare_spending(actual, planned)

        assert len(nudges) == 1

    def test_compare_spending_no_match(self, app):
        """Test no nudge when categories don't overlap."""
        from services.nudge_generator import _compare_spending

        actual = {"Food": 500.0}
        planned = {"Entertainment": 300.0}

        nudges = _compare_spending(actual, planned)

        assert len(nudges) == 0

    def test_compare_spending_zero_planned(self, app):
        """Test no nudge when planned amount is zero."""
        from services.nudge_generator import _compare_spending

        actual = {"Food": 500.0}
        planned = {"Food": 0.0}

        nudges = _compare_spending(actual, planned)

        assert len(nudges) == 0

    def test_get_goal_nudges_with_savings(self, app, sample_user_with_plaid_and_plan):
        """Test goal nudge when plan has savings."""
        from services.nudge_generator import _get_goal_nudges

        with app.app_context():
            nudges = _get_goal_nudges(sample_user_with_plaid_and_plan)

        assert len(nudges) == 1
        assert nudges[0]["type"] == "goal_reminder"
        assert "$1000" in nudges[0]["message"]

    def test_get_goal_nudges_no_plan(self, app, sample_user):
        """Test no goal nudge when user has no plan."""
        from services.nudge_generator import _get_goal_nudges

        with app.app_context():
            nudges = _get_goal_nudges(sample_user)

        assert len(nudges) == 0

    def test_generate_nudges_max_5(self, app, sample_user_with_plaid_and_plan):
        """Test that generate_nudges returns at most 5 nudges."""
        from services.nudge_generator import generate_nudges

        with app.app_context():
            nudges = generate_nudges(sample_user_with_plaid_and_plan)

        assert len(nudges) <= 5

    def test_generate_nudges_sorted_by_savings(self, app, sample_user_with_plaid_and_plan):
        """Test that nudges are sorted by potential savings (desc)."""
        from services.nudge_generator import generate_nudges

        with app.app_context():
            nudges = generate_nudges(sample_user_with_plaid_and_plan)

        savings = [n.get("potentialSavings", 0) for n in nudges]
        assert savings == sorted(savings, reverse=True)


# =============================================================================
# Database Model Tests
# =============================================================================

@pytest.mark.unit
class TestUserCategoryPreferenceModel:
    """Tests for the UserCategoryPreference model."""

    def test_create_preference(self, app):
        """Test creating a category preference."""
        from werkzeug.security import generate_password_hash

        with app.app_context():
            user = User(
                email="pref@test.com",
                password_hash=generate_password_hash("pass")
            )
            db.session.add(user)
            db.session.flush()

            pref = UserCategoryPreference(
                user_id=user.id,
                category_name="FOOD_AND_DRINK",
                display_order=0
            )
            db.session.add(pref)
            db.session.commit()

            saved = UserCategoryPreference.query.filter_by(user_id=user.id).first()
            assert saved is not None
            assert saved.category_name == "FOOD_AND_DRINK"
            assert saved.display_order == 0

    def test_user_name_column(self, app):
        """Test that User model has name column."""
        from werkzeug.security import generate_password_hash

        with app.app_context():
            user = User(
                email="nametest@test.com",
                password_hash=generate_password_hash("pass"),
                name="Test Name"
            )
            db.session.add(user)
            db.session.commit()

            saved = User.query.filter_by(email="nametest@test.com").first()
            assert saved.name == "Test Name"

    def test_user_name_nullable(self, app):
        """Test that name can be null."""
        from werkzeug.security import generate_password_hash

        with app.app_context():
            user = User(
                email="nonull@test.com",
                password_hash=generate_password_hash("pass")
            )
            db.session.add(user)
            db.session.commit()

            saved = User.query.filter_by(email="nonull@test.com").first()
            assert saved.name is None

    def test_user_category_preferences_relationship(self, app):
        """Test the user -> category_preferences relationship."""
        from werkzeug.security import generate_password_hash

        with app.app_context():
            user = User(
                email="rel@test.com",
                password_hash=generate_password_hash("pass")
            )
            db.session.add(user)
            db.session.flush()

            for i, cat in enumerate(["A", "B", "C"]):
                pref = UserCategoryPreference(
                    user_id=user.id,
                    category_name=cat,
                    display_order=i
                )
                db.session.add(pref)

            db.session.commit()

            saved_user = User.query.get(user.id)
            assert len(saved_user.category_preferences) == 3
