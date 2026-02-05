"""
Savings Progress Tool - Get user's progress toward savings goals.
"""

from tools.base import (
    Tool,
    ToolDefinition,
    ToolParameter,
    ToolContext,
    ToolResult,
    ToolCategory,
)


class SavingsProgressTool(Tool):
    """Tool for checking savings goals progress."""

    definition = ToolDefinition(
        name="get_savings_progress",
        display_name="Savings Progress",
        category=ToolCategory.TRACKING,
        version="2.0.0",

        description="Get the user's progress toward their savings goals. Shows each goal's target, current amount, and progress percentage.",

        when_to_use="ONLY use when the user asks about savings, saving goals, or their progress toward financial goals. Examples: 'how are my savings', 'savings progress', 'goal progress'.",

        when_not_to_use="Do NOT use for account balances, budget breakdowns, or spending status.",

        example_triggers=[
            "how are my savings",
            "savings progress",
            "goal progress",
            "am I on track for my goals",
            "how much have I saved",
            "savings goals",
        ],

        parameters=[
            ToolParameter(
                name="goal_name",
                type="string",
                description="Specific goal to check progress for. If not provided, shows all goals.",
                required=False,
                default=None
            ),
        ],

        requires=["authenticated"],
        produces=["data:savings_goals"],
        side_effects=[],
        confirmation_required=False,
        is_destructive=False,
        timeout_seconds=10,
        visual_type=None,  # Could add goal progress visualization later
    )

    async def execute(self, context: ToolContext) -> ToolResult:
        """Execute the savings progress retrieval."""
        from services.data_mock import get_savings_progress_data

        try:
            # Get savings progress data
            data = get_savings_progress_data()

            goals = data.get("goals", [])
            total_saved = data.get("total_saved", 0)
            total_target = data.get("total_target", 0)
            overall_progress = data.get("overall_progress", 0)
            monthly_target = data.get("monthly_savings_target", 0)

            # Filter by specific goal if requested
            goal_name = context.params.get("goal_name")
            if goal_name:
                matching_goals = [g for g in goals if g["name"].lower() == goal_name.lower()]
                if matching_goals:
                    goal = matching_goals[0]
                    message = (
                        f"Your '{goal['name']}' goal:\n"
                        f"- Target: ${goal['target']:,.2f}\n"
                        f"- Current: ${goal['current']:,.2f}\n"
                        f"- Remaining: ${goal['remaining']:,.2f}\n"
                        f"- Progress: {goal['progress_percent']:.1f}%"
                    )
                    return ToolResult.success_result(
                        data={"goal": goal},
                        message=message,
                        suggestions=[
                            "Show all my savings goals",
                            "How can I reach this goal faster?",
                            "Show my budget"
                        ]
                    )
                else:
                    return ToolResult.error_result(
                        f"No goal found with name '{goal_name}'",
                        "GOAL_NOT_FOUND"
                    )

            # Build message for all goals
            goal_lines = []
            for goal in goals:
                goal_lines.append(
                    f"- {goal['name']}: ${goal['current']:,.2f} of ${goal['target']:,.2f} "
                    f"({goal['progress_percent']:.1f}%)"
                )

            message = (
                f"Here's your savings progress:\n"
                f"{chr(10).join(goal_lines)}\n\n"
                f"Overall: ${total_saved:,.2f} saved toward ${total_target:,.2f} total "
                f"({overall_progress:.1f}% complete).\n"
                f"Monthly savings target: ${monthly_target:,.2f}"
            )

            return ToolResult.success_result(
                data={
                    "goals": goals,
                    "total_saved": total_saved,
                    "total_target": total_target,
                    "overall_progress": overall_progress,
                    "monthly_savings_target": monthly_target
                },
                message=message,
                visual=None,
                suggestions=[
                    "How can I save more?",
                    "Show my budget breakdown",
                    "Am I on track this month?"
                ]
            )

        except Exception as e:
            return ToolResult.error_result(
                f"Failed to retrieve savings progress: {str(e)}",
                "SAVINGS_PROGRESS_ERROR"
            )
