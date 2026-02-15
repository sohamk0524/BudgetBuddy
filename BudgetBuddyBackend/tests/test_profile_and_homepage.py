"""
Tests for user profile endpoints, top expenses, category preferences,
nudges endpoint, and name support in auth/onboarding.
"""

import pytest
import json
from datetime import date, timedelta
from db_models import db, User, UserCategoryPreference, SavedStatement, PlaidItem, PlaidAccount, BudgetPlan, FinancialProfile


# =============================================================================
# Auth Name Support (SMS-based)
# =============================================================================

@pytest.mark.integration
class TestAuthNameSupport:
    """Tests for name field in SMS auth and onboarding."""

    def test_verify_returns_name(self, client, sample_user_with_name):
        """Test that verify_code response includes the user's name."""
        from db_models import OTPCode
        with client.application.app_context():
            user = User.query.get(sample_user_with_name)
            phone = user.phone_number

        # Send code
        client.post("/v1/send_sms_code", json={"phone_number": phone})

        with client.application.app_context():
            otp = OTPCode.query.filter_by(phone_number=phone).first()
            code = otp.code

        response = client.post(
            "/v1/verify_code",
            json={"phone_number": phone, "code": code}
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert "name" in data
        assert data["name"] == "Test User"

    def test_verify_returns_null_name_when_unset(self, client, sample_user):
        """Test that verify returns null name when user has no name."""
        from db_models import OTPCode
        with client.application.app_context():
            user = User.query.get(sample_user)
            phone = user.phone_number

        client.post("/v1/send_sms_code", json={"phone_number": phone})

        with client.application.app_context():
            otp = OTPCode.query.filter_by(phone_number=phone).first()
            code = otp.code

        response = client.post(
            "/v1/verify_code",
            json={"phone_number": phone, "code": code}
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
                "isStudent": True,
                "budgetingGoal": "stability",
                "strictnessLevel": "moderate"
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
                "isStudent": False,
                "budgetingGoal": "stability"
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
        assert data["phoneNumber"] == "+15555550103"
        assert data["profile"] is not None
        assert data["profile"]["isStudent"] is False
        assert data["profile"]["budgetingGoal"] == "emergency_fund"
        assert data["profile"]["strictnessLevel"] == "moderate"
        assert isinstance(data["plaidItems"], list)

    def test_get_profile_no_profile(self, client, sample_user):
        """Test getting profile for user without financial profile."""
        response = client.get(f"/user/profile/{sample_user}")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["phoneNumber"] == "+15555550100"
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
                "isStudent": True,
                "budgetingGoal": "pay_debt",
                "strictnessLevel": "strict"
            }
        )

        assert response.status_code == 200

        # Verify
        response = client.get(f"/user/profile/{sample_user_with_name}")
        data = json.loads(response.data)
        assert data["profile"]["isStudent"] is True
        assert data["profile"]["budgetingGoal"] == "pay_debt"
        assert data["profile"]["strictnessLevel"] == "strict"

    def test_update_profile_partial(self, client, sample_user_with_name):
        """Test partial update only changes specified fields."""
        response = client.put(
            f"/user/profile/{sample_user_with_name}",
            json={"strictnessLevel": "relaxed"}
        )

        assert response.status_code == 200

        response = client.get(f"/user/profile/{sample_user_with_name}")
        data = json.loads(response.data)
        assert data["profile"]["strictnessLevel"] == "relaxed"
        assert data["profile"]["budgetingGoal"] == "emergency_fund"  # Unchanged
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

        # FOOD_AND_DRINK should be the highest (displayed as "Food & Drink")
        assert data["topExpenses"][0]["category"] == "Food & Drink"
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

        # Find the food nudge (displayed as "Food & Drink")
        food_nudges = [n for n in data["nudges"] if n.get("category") == "Food & Drink"]
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
        with app.app_context():
            user = User(phone_number="+15555550600")
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
        with app.app_context():
            user = User(
                phone_number="+15555550601",
                name="Test Name"
            )
            db.session.add(user)
            db.session.commit()

            saved = User.query.filter_by(phone_number="+15555550601").first()
            assert saved.name == "Test Name"

    def test_user_name_nullable(self, app):
        """Test that name can be null."""
        with app.app_context():
            user = User(phone_number="+15555550602")
            db.session.add(user)
            db.session.commit()

            saved = User.query.filter_by(phone_number="+15555550602").first()
            assert saved.name is None

    def test_user_category_preferences_relationship(self, app):
        """Test the user -> category_preferences relationship."""
        with app.app_context():
            user = User(phone_number="+15555550603")
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


# =============================================================================
# Financial Summary Endpoint
# =============================================================================

@pytest.mark.integration
class TestFinancialSummaryEndpoint:
    """Tests for GET /user/financial-summary with Plaid-first logic."""

    def test_plaid_user_net_worth(self, client, app):
        """Plaid-linked user: net worth = assets - liabilities."""
        with app.app_context():
            user = User(phone_number="+15555550700")
            db.session.add(user)
            db.session.flush()

            item = PlaidItem(
                user_id=user.id, item_id="fs-item-1",
                access_token_encrypted=b'tok', institution_name="Bank", status="active"
            )
            db.session.add(item)
            db.session.flush()

            # Depository (asset): 5000
            db.session.add(PlaidAccount(
                plaid_item_id=item.id, account_id="fs-acct-chk",
                name="Checking", account_type="depository", account_subtype="checking",
                balance_current=3000.0, balance_available=2800.0
            ))
            # Investment (asset): 10000
            db.session.add(PlaidAccount(
                plaid_item_id=item.id, account_id="fs-acct-inv",
                name="Brokerage", account_type="investment",
                balance_current=10000.0
            ))
            # Credit (liability): 1500
            db.session.add(PlaidAccount(
                plaid_item_id=item.id, account_id="fs-acct-cc",
                name="Credit Card", account_type="credit", account_subtype="credit card",
                balance_current=1500.0
            ))
            db.session.commit()
            uid = user.id

        response = client.get(f"/user/financial-summary?userId={uid}")
        assert response.status_code == 200
        data = json.loads(response.data)

        assert data["hasData"] is True
        assert data["source"] == "plaid"
        # 3000 + 10000 - 1500 = 11500
        assert data["netWorth"] == 11500.0
        assert data["statementInfo"] is None

    def test_plaid_user_safe_to_spend_from_plan(self, client, sample_user_with_plaid_and_plan):
        """Plaid user with budget plan: safe to spend from plan's safeToSpend."""
        response = client.get(f"/user/financial-summary?userId={sample_user_with_plaid_and_plan}")

        assert response.status_code == 200
        data = json.loads(response.data)

        assert data["hasData"] is True
        assert data["source"] == "plaid"
        assert data["safeToSpend"] == 1500.0

    def test_plaid_user_safe_to_spend_no_plan(self, client, app):
        """Plaid user without plan: safe to spend = sum of depository balance_available."""
        with app.app_context():
            user = User(phone_number="+15555550701")
            db.session.add(user)
            db.session.flush()

            item = PlaidItem(
                user_id=user.id, item_id="fs-item-noplan",
                access_token_encrypted=b'tok', institution_name="Bank", status="active"
            )
            db.session.add(item)
            db.session.flush()

            db.session.add(PlaidAccount(
                plaid_item_id=item.id, account_id="fs-acct-noplan-chk",
                name="Checking", account_type="depository", account_subtype="checking",
                balance_current=2000.0, balance_available=1800.0
            ))
            db.session.add(PlaidAccount(
                plaid_item_id=item.id, account_id="fs-acct-noplan-sav",
                name="Savings", account_type="depository", account_subtype="savings",
                balance_current=5000.0, balance_available=5000.0
            ))
            db.session.commit()
            uid = user.id

        response = client.get(f"/user/financial-summary?userId={uid}")
        data = json.loads(response.data)

        assert data["source"] == "plaid"
        # 1800 + 5000 = 6800
        assert data["safeToSpend"] == 6800.0

    def test_statement_fallback(self, client, app):
        """Statement-only user: fallback to statement logic, source='statement'."""
        with app.app_context():
            user = User(phone_number="+15555550702")
            db.session.add(user)
            db.session.flush()

            stmt = SavedStatement(
                user_id=user.id, filename="jan.pdf", file_type="pdf",
                raw_file=b'pdf-bytes', ending_balance=10000.0,
                total_income=5000.0, total_expenses=3000.0
            )
            db.session.add(stmt)
            db.session.commit()
            uid = user.id

        response = client.get(f"/user/financial-summary?userId={uid}")
        data = json.loads(response.data)

        assert data["hasData"] is True
        assert data["source"] == "statement"
        assert data["netWorth"] == 10000.0
        assert data["safeToSpend"] == 800.0  # 0.08 * 10000
        assert data["statementInfo"] is not None
        assert data["statementInfo"]["filename"] == "jan.pdf"

    def test_no_data_user(self, client, sample_user):
        """User with neither Plaid nor statement: hasData=false, nulls."""
        response = client.get(f"/user/financial-summary?userId={sample_user}")

        assert response.status_code == 200
        data = json.loads(response.data)

        assert data["hasData"] is False
        assert data["source"] == "none"
        assert data["netWorth"] is None
        assert data["safeToSpend"] is None
        assert data["statementInfo"] is None
        assert data["spendingBreakdown"] is None
