"""
Spending Status Tool - Check if user is on track with burndown visualization.
"""

from tools.base import (
    Tool,
    ToolDefinition,
    ToolParameter,
    ToolContext,
    ToolResult,
    ToolCategory,
)
from models import VisualPayload


class SpendingStatusTool(Tool):
    """Tool for checking spending status with burndown chart visualization."""

    definition = ToolDefinition(
        name="get_spending_status",
        display_name="Spending Status",
        category=ToolCategory.TRACKING,
        version="2.0.0",

        description="Check if the user is on track with their budget and spending pace. Shows current spending vs budget with a burndown chart.",

        when_to_use="ONLY use when the user asks about affordability (can I afford X?), spending pace, budget status, or if they're overspending. Examples: 'am I overspending', 'can I afford this', 'how am I doing'.",

        when_not_to_use="Do NOT use for greetings, general questions, or requests to see budget breakdown (use get_budget_overview instead).",

        example_triggers=[
            "am I overspending",
            "can I afford",
            "how am I doing",
            "budget status",
            "spending pace",
            "am I on track",
        ],

        parameters=[
            ToolParameter(
                name="category",
                type="string",
                description="Specific category to check status for. If not provided, checks overall spending.",
                required=False,
                default=None
            ),
            ToolParameter(
                name="purchase_amount",
                type="number",
                description="Amount of a potential purchase to evaluate affordability.",
                required=False,
                default=None,
                min_value=0
            ),
        ],

        requires=["authenticated"],
        produces=["data:spending_status", "visual:burndownChart"],
        side_effects=[],
        confirmation_required=False,
        is_destructive=False,
        timeout_seconds=10,
        visual_type="burndownChart",
    )

    async def execute(self, context: ToolContext) -> ToolResult:
        """Execute the spending status check."""
        from services.data_mock import get_spending_status_data

        try:
            # Get spending status data
            data = get_spending_status_data()

            spent = data.get("spent", 0)
            budget = data.get("budget", 0)
            ideal_pace = data.get("idealPace", 0)
            status = data.get("status", "unknown")
            status_message = data.get("statusMessage", "")
            daily_budget_remaining = data.get("dailyBudgetRemaining", 0)
            days_remaining = data.get("daysRemaining", 0)

            # Handle purchase affordability check
            purchase_amount = context.params.get("purchase_amount")
            if purchase_amount is not None:
                remaining_budget = budget - spent
                can_afford = purchase_amount <= remaining_budget

                if can_afford:
                    message = (
                        f"Yes, you can afford ${purchase_amount:,.2f}! "
                        f"You have ${remaining_budget:,.2f} remaining in your budget. "
                        f"After this purchase, you'd have ${remaining_budget - purchase_amount:,.2f} left."
                    )
                else:
                    message = (
                        f"This ${purchase_amount:,.2f} purchase would exceed your remaining budget of ${remaining_budget:,.2f}. "
                        f"You'd be ${purchase_amount - remaining_budget:,.2f} over budget."
                    )
            else:
                # General status message
                message = (
                    f"{status_message} "
                    f"You've spent ${spent:,.2f} of your ${budget:,.2f} budget. "
                    f"With {days_remaining} days left, you can spend ${daily_budget_remaining:,.2f}/day."
                )

            # Create visual payload
            visual = VisualPayload.burndown_chart(
                spent=spent,
                budget=budget,
                ideal_pace=ideal_pace
            )

            return ToolResult.success_result(
                data={
                    "spent": spent,
                    "budget": budget,
                    "idealPace": ideal_pace,
                    "status": status,
                    "daysRemaining": days_remaining,
                    "dailyBudgetRemaining": daily_budget_remaining,
                    "projectedEndOfMonth": data.get("projectedEndOfMonth", 0),
                    "categoryBreakdown": data.get("categoryBreakdown", {})
                },
                message=message,
                visual=visual,
                suggestions=[
                    "Show my budget breakdown",
                    "Which category am I overspending in?",
                    "How can I save more this month?"
                ]
            )

        except Exception as e:
            return ToolResult.error_result(
                f"Failed to retrieve spending status: {str(e)}",
                "SPENDING_STATUS_ERROR"
            )
