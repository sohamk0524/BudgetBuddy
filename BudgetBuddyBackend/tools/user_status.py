"""
User Status Tools for BudgetBuddy.
Tools for checking user setup status and guiding them through onboarding.
"""

import logging
from typing import Any, Dict, List, Optional

from tools.base import (
    Tool,
    ToolDefinition,
    ToolParameter,
    ToolContext,
    ToolResult,
    ToolCategory,
)

logger = logging.getLogger(__name__)


class CheckUserSetupStatusTool(Tool):
    """
    Tool to check if the user has completed their financial setup.
    This should be called FIRST before any budget/spending tools.
    """

    definition = ToolDefinition(
        name="check_user_setup_status",
        display_name="Check Setup Status",
        category=ToolCategory.ACCOUNT_MANAGEMENT,
        version="1.0.0",
        description="Check if the user has completed their profile and budget plan setup. IMPORTANT: Always call this FIRST when a user asks about their budget, spending, or finances to determine if they have the necessary setup completed.",
        when_to_use="Call this FIRST when the user asks about budget, spending, finances, or any financial data. This tells you if they have a profile and budget plan so you can either help them set up or proceed with their request.",
        when_not_to_use="Do not use for greetings, general questions, or non-financial topics.",
        example_triggers=[
            "help me with my budget",
            "show my spending",
            "can I afford this",
            "how am I doing financially",
            "check my finances"
        ],
        parameters=[],  # No parameters needed - uses context.user_id
        returns_schema={
            "type": "object",
            "properties": {
                "has_profile": {"type": "boolean"},
                "profile_complete": {"type": "boolean"},
                "has_budget_plan": {"type": "boolean"},
                "has_statement": {"type": "boolean"},
                "is_fully_setup": {"type": "boolean"},
                "missing_items": {"type": "array", "items": {"type": "string"}},
                "next_step": {"type": "string"},
                "message": {"type": "string"}
            }
        },
        requires=[],  # No prerequisites - this is the first check
        produces=["user_status"],
        side_effects=[],
        confirmation_required=False,
        timeout_seconds=10
    )

    async def execute(self, context: ToolContext) -> ToolResult:
        """Check user's setup status."""
        user_id = context.user_id

        try:
            from db_models import User, BudgetPlan, SavedStatement, FinancialProfile

            has_profile = False
            has_plan = False
            has_statement = False
            profile_complete = False

            # Check profile
            profile = FinancialProfile.query.filter_by(user_id=user_id).first()
            if profile:
                has_profile = True
                profile_complete = profile.monthly_income is not None and profile.monthly_income > 0

            # Check budget plan
            plan = BudgetPlan.query.filter_by(user_id=user_id).first()
            has_plan = plan is not None

            # Check statements
            statement = SavedStatement.query.filter_by(user_id=user_id).first()
            has_statement = statement is not None

            # Determine what's missing and provide guidance
            missing_items = []
            next_step = None
            ui_action = None

            if not has_profile or not profile_complete:
                missing_items.append("financial profile")
                next_step = "complete_profile"
                ui_action = "open_profile_setup"
            elif not has_plan:
                missing_items.append("budget plan")
                next_step = "create_budget_plan"
                ui_action = "open_budget_creator"

            is_fully_setup = has_profile and profile_complete and has_plan
            message = self._get_setup_message(has_profile, profile_complete, has_plan)

            data = {
                "has_profile": has_profile,
                "profile_complete": profile_complete,
                "has_budget_plan": has_plan,
                "has_statement": has_statement,
                "is_fully_setup": is_fully_setup,
                "missing_items": missing_items,
                "next_step": next_step,
                "ui_action": ui_action,
                "message": message
            }

            # Build suggestions based on status
            suggestions = []
            if not is_fully_setup:
                if not has_profile or not profile_complete:
                    suggestions.append("Set up your financial profile")
                elif not has_plan:
                    suggestions.append("Create a budget plan")
            else:
                suggestions = [
                    "Show me my budget overview",
                    "How am I doing on spending?",
                    "Check my savings progress"
                ]

            return ToolResult.success_result(
                data=data,
                message=message,
                suggestions=suggestions
            )

        except Exception as e:
            logger.error(f"Error checking user status for user {user_id}: {e}")
            return ToolResult.error_result(
                f"Unable to check your account status: {str(e)}",
                "DATABASE_ERROR"
            )

    def _get_setup_message(self, has_profile: bool, profile_complete: bool, has_plan: bool) -> str:
        """Generate a helpful message based on user's setup status."""
        if not has_profile or not profile_complete:
            return "I'd love to help with your budget! First, let's set up your financial profile so I can give you personalized advice. Would you like to do that now?"
        elif not has_plan:
            return "You have your profile set up, but you haven't created a budget plan yet. A budget plan helps you track spending and reach your goals. Would you like to create one together?"
        else:
            return "You're all set up! I can help you track your spending, check your budget, or answer any financial questions."


class SuggestNextActionTool(Tool):
    """
    Tool to suggest the next action for users who haven't completed setup.
    """

    definition = ToolDefinition(
        name="suggest_next_action",
        display_name="Suggest Next Action",
        category=ToolCategory.ACCOUNT_MANAGEMENT,
        version="1.0.0",
        description="Suggest the next action for users based on their setup status. Use this to guide users who need to complete their profile or create a budget plan.",
        when_to_use="Use after check_user_setup_status shows that the user is not fully set up. This provides specific guidance and UI actions to help them complete setup.",
        when_not_to_use="Do not use if the user is already fully set up (has profile and budget plan).",
        example_triggers=[
            "what should I do next",
            "help me get started",
            "how do I set up my budget"
        ],
        parameters=[],  # No parameters needed
        returns_schema={
            "type": "object",
            "properties": {
                "action": {"type": "string"},
                "message": {"type": "string"},
                "ui_action": {"type": "string"},
                "cta_text": {"type": "string"}
            }
        },
        requires=[],
        produces=["next_action_suggestion"],
        side_effects=[],
        confirmation_required=False,
        timeout_seconds=10
    )

    async def execute(self, context: ToolContext) -> ToolResult:
        """Suggest the next action for the user."""
        user_id = context.user_id

        try:
            from db_models import BudgetPlan, FinancialProfile

            has_profile = False
            profile_complete = False
            has_plan = False

            # Check profile
            profile = FinancialProfile.query.filter_by(user_id=user_id).first()
            if profile:
                has_profile = True
                profile_complete = profile.monthly_income is not None and profile.monthly_income > 0

            # Check budget plan
            plan = BudgetPlan.query.filter_by(user_id=user_id).first()
            has_plan = plan is not None

            if not has_profile or not profile_complete:
                data = {
                    "action": "complete_profile",
                    "message": "Let's start by setting up your financial profile. This helps me understand your income, expenses, and financial goals so I can give you personalized advice.",
                    "ui_action": "open_profile_setup",
                    "cta_text": "Set Up Profile"
                }
                return ToolResult.success_result(
                    data=data,
                    message=data["message"],
                    suggestions=["Set up my profile", "What information do you need?"]
                )

            if not has_plan:
                data = {
                    "action": "create_budget_plan",
                    "message": "Now let's create your personalized budget plan. I'll help you allocate your income across different categories and set savings goals.",
                    "ui_action": "open_budget_creator",
                    "cta_text": "Create Budget Plan"
                }
                return ToolResult.success_result(
                    data=data,
                    message=data["message"],
                    suggestions=["Create my budget plan", "How does budgeting work?"]
                )

            # User is fully set up
            data = {
                "action": "none_required",
                "message": "You're all set! What would you like to know about your finances?",
                "ui_action": None,
                "suggestions": [
                    "Show me my budget overview",
                    "How am I doing on spending this month?",
                    "Check my savings progress"
                ]
            }
            return ToolResult.success_result(
                data=data,
                message=data["message"],
                suggestions=data["suggestions"]
            )

        except Exception as e:
            logger.error(f"Error suggesting next action for user {user_id}: {e}")
            return ToolResult.error_result(
                f"Unable to determine next steps: {str(e)}",
                "DATABASE_ERROR"
            )
