"""
Plan Generator Service - Generates personalized spending plans using AI.
"""

import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from models import AssistantResponse
from services.llm_service import Agent


# System prompt for plan generation
PLAN_GENERATION_PROMPT = """You are BudgetBuddy's financial planning assistant. Generate a personalized monthly spending plan based on the user's financial data.

USER PROFILE:
- Student: {is_student}
- Budgeting Goal: {budgeting_goal}
- Strictness Level: {strictness_level}
- Monthly Income: ${monthly_income:,.2f}

FINANCIAL SITUATION:
- Housing Situation: {housing_situation}
- Fixed Expenses: ${fixed_expenses:,.2f}
- Debt Types: {debt_types}

DETAILED EXPENSES FROM DEEP DIVE:
{detailed_expenses}

UPCOMING EVENTS:
{upcoming_events}

SAVINGS GOALS:
{savings_goals}

USER PREFERENCES:
{preferences}

HISTORICAL SPENDING BREAKDOWN (last 30 days, if available):
{spending_breakdown}

INSTRUCTIONS:
1. Calculate total monthly expenses and Safe-to-Spend amount
2. Allocate funds to each category with specific dollar amounts
3. Account for upcoming events (prorate if user wants to save gradually)
4. Provide 3-5 actionable, personalized recommendations
5. Flag any warnings (overspending, income doesn't cover expenses, etc.)
6. Use the 50/30/20 rule as a guideline but adapt to user's financial personality
7. For each category, include an "essentialSplit" showing the essential vs. discretionary breakdown based on historical data

OUTPUT FORMAT (respond ONLY with valid JSON, no other text):
{{
    "summary": "A 2-3 sentence overview of their financial health and plan",
    "safeToSpend": <number - discretionary amount after all obligations>,
    "totalIncome": <number>,
    "totalExpenses": <number>,
    "totalSavings": <number>,
    "totalEssential": <number - total essential spending from all categories>,
    "totalDiscretionary": <number - total discretionary spending from all categories>,
    "categoryAllocations": [
        {{"id": "fixed", "name": "Fixed Essentials", "amount": <number>, "color": "#FF6B6B", "items": [{{"name": "Rent", "amount": <number>}}, ...], "essentialAmount": <number>, "discretionaryAmount": <number>}},
        {{"id": "flexible", "name": "Flexible Spending", "amount": <number>, "color": "#4ECDC4", "items": [...], "essentialAmount": <number>, "discretionaryAmount": <number>}},
        {{"id": "discretionary", "name": "Fun Money", "amount": <number>, "color": "#45B7D1", "items": [...], "essentialAmount": 0, "discretionaryAmount": <number>}},
        {{"id": "savings", "name": "Savings Goals", "amount": <number>, "color": "#96CEB4", "items": [...], "essentialAmount": <number>, "discretionaryAmount": 0}},
        {{"id": "events", "name": "Upcoming Events", "amount": <number>, "color": "#FFEAA7", "items": [...], "essentialAmount": 0, "discretionaryAmount": <number>}}
    ],
    "recommendations": [
        {{"category": "groceries", "title": "Short actionable title", "description": "Detailed explanation", "potentialSavings": <number or null>}},
        ...
    ],
    "warnings": ["Warning message if applicable", ...]
}}

Be encouraging but honest. Adapt recommendations to their financial personality."""


# Agent is created per-request in generate_plan() since the system prompt
# is personalized with user data each time.


def get_full_user_profile(user_id: int) -> Optional[Dict[str, Any]]:
    """Fetch user's complete financial profile from database."""
    try:
        from db_models import get_user, get_profile
        user = get_user(user_id)
        if user:
            profile = get_profile(user_id)
            if profile:
                debt_types = []
                raw_debt = profile.get('debt_types')
                if raw_debt:
                    try:
                        debt_types = json.loads(raw_debt)
                    except Exception:
                        debt_types = []

                return {
                    "is_student": profile.get('is_student') or False,
                    "budgeting_goal": profile.get('budgeting_goal') or "stability",
                    "strictness_level": profile.get('strictness_level') or "moderate",
                    "fixed_expenses": profile.get('fixed_expenses') or 0,
                    "savings_goal_name": profile.get('savings_goal_name') or "",
                    "savings_goal_target": profile.get('savings_goal_target') or 0,
                    "housing_situation": profile.get('housing_situation') or "rent",
                    "debt_types": debt_types,
                }
    except Exception as e:
        print(f"Error fetching user profile: {e}")
    return None


def format_deep_dive_data(deep_dive_data: Dict[str, Any]) -> str:
    """Format deep dive data for the prompt."""
    lines = []

    # Fixed expenses
    fixed = deep_dive_data.get("fixedExpenses", {})
    if fixed:
        lines.append("Fixed Expenses:")
        if fixed.get("rent"):
            lines.append(f"  - Rent/Mortgage: ${fixed['rent']:,.2f}")
        if fixed.get("utilities"):
            lines.append(f"  - Utilities: ${fixed['utilities']:,.2f}")
        subscriptions = fixed.get("subscriptions", [])
        if subscriptions:
            total_subs = sum(s.get("amount", 0) for s in subscriptions)
            lines.append(f"  - Subscriptions: ${total_subs:,.2f}")
            for sub in subscriptions:
                lines.append(f"    * {sub.get('name', 'Unknown')}: ${sub.get('amount', 0):,.2f}")

    # Variable spending
    variable = deep_dive_data.get("variableSpending", {})
    if variable:
        lines.append("\nVariable Spending:")
        if variable.get("groceries"):
            lines.append(f"  - Groceries: ${variable['groceries']:,.2f}/month")
        transport = variable.get("transportation", {})
        if isinstance(transport, dict):
            total_transport = transport.get("gas", 0) + transport.get("insurance", 0) + transport.get("transitPass", 0)
            transport_type = transport.get("type", "car")
            lines.append(f"  - Transportation ({transport_type}): ${total_transport:,.2f}")
        elif transport:
            lines.append(f"  - Transportation: ${transport:,.2f}")
        if variable.get("diningEntertainment"):
            lines.append(f"  - Dining & Entertainment: ${variable['diningEntertainment']:,.2f}")

    return "\n".join(lines) if lines else "No detailed expenses provided"


def format_upcoming_events(events: List[Dict[str, Any]]) -> str:
    """Format upcoming events for the prompt."""
    if not events:
        return "No upcoming events"

    lines = []
    for event in events:
        name = event.get("name", "Unknown event")
        cost = event.get("cost", 0)
        date = event.get("date", "Unknown date")
        save_gradually = event.get("saveGradually", False)
        approach = "Save gradually" if save_gradually else "Pay when due"
        lines.append(f"  - {name}: ${cost:,.2f} on {date} ({approach})")

    return "\n".join(lines)


def format_savings_goals(goals: List[Dict[str, Any]]) -> str:
    """Format savings goals for the prompt."""
    if not goals:
        return "No specific savings goals"

    lines = []
    for goal in goals:
        name = goal.get("name", "Unknown goal")
        target = goal.get("target", 0)
        current = goal.get("current", 0)
        priority = goal.get("priority", 99)
        progress = (current / target * 100) if target > 0 else 0
        lines.append(f"  - {name}: ${current:,.2f} / ${target:,.2f} ({progress:.0f}% complete, priority {priority})")

    return "\n".join(lines)


def get_spending_breakdown(user_id: int) -> str:
    """Get spending breakdown by category from classified transactions."""
    try:
        from db_models import PlaidItem, Transaction

        plaid_items = PlaidItem.query.filter_by(user_id=user_id, status="active").all()
        account_ids = []
        for item in plaid_items:
            for account in item.accounts:
                account_ids.append(account.id)

        if not account_ids:
            return "No transaction data available"

        start_date = (datetime.now() - timedelta(days=30)).date()
        transactions = Transaction.query.filter(
            Transaction.plaid_account_id.in_(account_ids),
            Transaction.date >= start_date,
            Transaction.amount > 0
        ).all()

        if not transactions:
            return "No recent transactions"

        # Aggregate by sub_category (food, drink, transportation, entertainment, other)
        category_totals = {"food": 0.0, "drink": 0.0, "transportation": 0.0, "entertainment": 0.0, "other": 0.0, "unclassified": 0.0}

        for txn in transactions:
            sub = getattr(txn, 'sub_category', None) or 'unclassified'
            if sub in category_totals:
                category_totals[sub] += txn.amount
            else:
                category_totals['unclassified'] += txn.amount

        lines = ["Spending by category (last 30 days):"]
        for cat, total in sorted(category_totals.items(), key=lambda x: x[1], reverse=True):
            if total > 0:
                lines.append(f"  {cat.capitalize()}: ${total:,.2f}")

        return "\n".join(lines)

    except Exception as e:
        print(f"Error getting spending breakdown: {e}")
        return "Unable to retrieve spending breakdown"


def format_preferences(prefs: Dict[str, Any]) -> str:
    """Format spending preferences for the prompt."""
    if not prefs:
        return "No preferences specified"

    lines = []
    style = prefs.get("spendingStyle", 0.5)
    style_desc = "Frugal" if style < 0.3 else "Liberal" if style > 0.7 else "Moderate"
    lines.append(f"  - Spending Style: {style_desc} ({style:.1f})")

    priorities = prefs.get("priorities", [])
    if priorities:
        lines.append(f"  - Priorities: {', '.join(priorities)}")

    strictness = prefs.get("strictness", "moderate")
    lines.append(f"  - Budget Strictness: {strictness}")

    return "\n".join(lines)


def generate_plan(user_id: int, deep_dive_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate a personalized spending plan using AI.

    Args:
        user_id: The user's ID
        deep_dive_data: Data collected from the question flow

    Returns:
        Dictionary containing the generated plan
    """
    # Get user's profile
    profile = get_full_user_profile(user_id)
    if not profile:
        return {
            "error": "User profile not found",
            "textMessage": "Please complete onboarding first.",
            "plan": None
        }

    # Get housing and debt from deep_dive_data (now collected during plan creation)
    housing_situation = deep_dive_data.get("housingSituation", profile.get("housing_situation", "rent"))
    debt_types = deep_dive_data.get("debtTypes", profile.get("debt_types", []))

    # Calculate fixed expenses from deep dive data
    fixed_expenses_data = deep_dive_data.get("fixedExpenses", {})
    rent = fixed_expenses_data.get("rent", 0)
    utilities = fixed_expenses_data.get("utilities", 0)
    subscriptions = sum(s.get("amount", 0) for s in fixed_expenses_data.get("subscriptions", []))
    calculated_fixed = rent + utilities + subscriptions

    # Income comes from deep_dive_data (collected during plan creation, not onboarding)
    monthly_income = deep_dive_data.get("monthlyIncome", 0)

    # Format the prompt with user data
    prompt_data = {
        "is_student": "Yes" if profile.get("is_student") else "No",
        "budgeting_goal": (profile.get("budgeting_goal", "stability") or "stability").replace("_", " ").title(),
        "strictness_level": (profile.get("strictness_level", "moderate") or "moderate").replace("_", " ").title(),
        "monthly_income": monthly_income,
        "housing_situation": housing_situation.replace("_", " ").title(),
        "fixed_expenses": calculated_fixed if calculated_fixed > 0 else profile.get("fixed_expenses", 0),
        "debt_types": ", ".join(d.replace("_", " ").title() for d in debt_types) if debt_types else "None",
        "detailed_expenses": format_deep_dive_data(deep_dive_data),
        "upcoming_events": format_upcoming_events(deep_dive_data.get("upcomingEvents", [])),
        "savings_goals": format_savings_goals(deep_dive_data.get("savingsGoals", [])),
        "preferences": format_preferences(deep_dive_data.get("spendingPreferences", {})),
        "spending_breakdown": get_spending_breakdown(user_id)
    }

    system_prompt = PLAN_GENERATION_PROMPT.format(**prompt_data)

    try:
        # Create a plan-generation agent with the personalized prompt
        plan_agent = Agent(
            name="BudgetPlanGenerator",
            instructions=system_prompt,
            model="claude-opus-4-6",
        )

        # Check if the LLM provider is available
        if not plan_agent.is_available():
            return generate_fallback_plan(profile, deep_dive_data)

        # Run the agent
        result = plan_agent.run(
            "Generate my personalized spending plan based on the data provided. Respond only with valid JSON."
        )
        response_text = result.get("content", "")

        # Parse the JSON response
        try:
            # Try to extract JSON from the response
            json_match = response_text
            if "```json" in response_text:
                json_match = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                json_match = response_text.split("```")[1].split("```")[0]

            plan_data = json.loads(json_match.strip())

            # Add computed fields
            plan_data["daysRemaining"] = days_remaining_in_month()
            plan_data["budgetUsedPercent"] = 0  # Would need transaction data
            plan_data["createdAt"] = datetime.now().isoformat()

            return {
                "textMessage": "Your personalized spending plan is ready!",
                "plan": plan_data,
                "visualPayload": {
                    "type": "spendingPlan",
                    "safeToSpend": plan_data.get("safeToSpend", 0),
                    "categories": plan_data.get("categoryAllocations", [])
                }
            }

        except json.JSONDecodeError as e:
            print(f"Failed to parse LLM response as JSON: {e}")
            print(f"Response was: {response_text}")
            return generate_fallback_plan(profile, deep_dive_data)

    except Exception as e:
        print(f"Error generating plan: {e}")
        return generate_fallback_plan(profile, deep_dive_data)


def days_remaining_in_month() -> int:
    """Calculate days remaining in the current month."""
    today = datetime.now()
    if today.month == 12:
        next_month = today.replace(year=today.year + 1, month=1, day=1)
    else:
        next_month = today.replace(month=today.month + 1, day=1)
    return (next_month - today).days


def generate_fallback_plan(profile: Dict[str, Any], deep_dive_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate a basic plan without AI when the LLM is unavailable.
    Uses simple rules-based allocation.
    """
    income = deep_dive_data.get("monthlyIncome", 0)
    fixed_from_profile = profile.get("fixed_expenses", 0)

    # Calculate from deep dive data
    fixed_expenses = deep_dive_data.get("fixedExpenses", {})
    rent = fixed_expenses.get("rent", 0)
    utilities = fixed_expenses.get("utilities", 0)
    subscriptions = sum(s.get("amount", 0) for s in fixed_expenses.get("subscriptions", []))
    total_fixed = rent + utilities + subscriptions

    # If no deep dive data, use profile
    if total_fixed == 0:
        total_fixed = fixed_from_profile

    variable = deep_dive_data.get("variableSpending", {})
    groceries = variable.get("groceries", income * 0.1)
    transport = variable.get("transportation", {})
    transport_total = (transport.get("gas", 0) + transport.get("insurance", 0) + transport.get("transitPass", 0)) if isinstance(transport, dict) else 0
    dining = variable.get("diningEntertainment", income * 0.05)

    total_flexible = groceries + transport_total
    total_discretionary = dining

    # Calculate savings
    events = deep_dive_data.get("upcomingEvents", [])
    events_monthly = sum(e.get("cost", 0) / 3 for e in events if e.get("saveGradually", False))

    savings_goals = deep_dive_data.get("savingsGoals", [])
    savings_monthly = income * 0.1  # Default 10% savings

    total_expenses = total_fixed + total_flexible + total_discretionary + savings_monthly + events_monthly
    safe_to_spend = income - total_expenses

    # Build category allocations
    categories = [
        {
            "id": "fixed",
            "name": "Fixed Essentials",
            "amount": total_fixed,
            "color": "#FF6B6B",
            "items": [
                {"name": "Rent/Mortgage", "amount": rent or fixed_from_profile * 0.6},
                {"name": "Utilities", "amount": utilities or fixed_from_profile * 0.2},
                {"name": "Subscriptions", "amount": subscriptions or fixed_from_profile * 0.1}
            ]
        },
        {
            "id": "flexible",
            "name": "Flexible Spending",
            "amount": total_flexible,
            "color": "#4ECDC4",
            "items": [
                {"name": "Groceries", "amount": groceries},
                {"name": "Transportation", "amount": transport_total}
            ]
        },
        {
            "id": "discretionary",
            "name": "Fun Money",
            "amount": total_discretionary,
            "color": "#45B7D1",
            "items": [
                {"name": "Dining & Entertainment", "amount": dining}
            ]
        },
        {
            "id": "savings",
            "name": "Savings Goals",
            "amount": savings_monthly,
            "color": "#96CEB4",
            "items": [{"name": profile.get("savings_goal_name", "General Savings"), "amount": savings_monthly}]
        }
    ]

    if events_monthly > 0:
        categories.append({
            "id": "events",
            "name": "Upcoming Events",
            "amount": events_monthly,
            "color": "#FFEAA7",
            "items": [{"name": e.get("name", "Event"), "amount": e.get("cost", 0) / 3} for e in events if e.get("saveGradually")]
        })

    # Generate recommendations
    recommendations = []

    if income > 0 and total_fixed / income > 0.5:
        recommendations.append({
            "category": "housing",
            "title": "High fixed costs",
            "description": f"Your fixed expenses are {total_fixed/income*100:.0f}% of income. Consider reducing subscriptions.",
            "potentialSavings": subscriptions * 0.3
        })

    if safe_to_spend < income * 0.1:
        recommendations.append({
            "category": "general",
            "title": "Low discretionary buffer",
            "description": "Your Safe-to-Spend amount is limited. Look for areas to reduce spending.",
            "potentialSavings": None
        })

    if savings_monthly < income * 0.2:
        recommendations.append({
            "category": "savings",
            "title": "Increase savings",
            "description": "Try to save at least 20% of your income for long-term financial health.",
            "potentialSavings": None
        })

    plan = {
        "summary": f"Based on your ${income:,.2f} monthly income, you have ${safe_to_spend:,.2f} safe to spend after covering essentials and savings. {'Your budget is tight - consider reducing discretionary spending.' if safe_to_spend < income * 0.15 else 'You have a healthy buffer for unexpected expenses.'}",
        "safeToSpend": max(0, safe_to_spend),
        "totalIncome": income,
        "totalExpenses": total_expenses,
        "totalSavings": savings_monthly,
        "daysRemaining": days_remaining_in_month(),
        "budgetUsedPercent": 0,
        "categoryAllocations": categories,
        "recommendations": recommendations,
        "warnings": ["Budget generated without AI - estimates may need adjustment."] if safe_to_spend < 0 else [],
        "createdAt": datetime.now().isoformat()
    }

    return {
        "textMessage": "Your spending plan is ready! (Generated with basic rules - AI unavailable)",
        "plan": plan,
        "visualPayload": {
            "type": "spendingPlan",
            "safeToSpend": plan["safeToSpend"],
            "categories": categories
        }
    }


def save_plan_to_db(user_id: int, plan: Dict[str, Any]) -> bool:
    """Save the generated plan to the database."""
    try:
        from db_models import create_plan
        from datetime import datetime
        create_plan(user_id, json.dumps(plan), datetime.now().strftime("%Y-%m"))
        return True
    except Exception as e:
        print(f"Error saving plan to database: {e}")
        return False
