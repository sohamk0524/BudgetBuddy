"""
Manage Goals Tools - Create, update, and contribute to savings goals.
"""

from datetime import datetime, date
from dateutil.relativedelta import relativedelta

from tools.base import (
    Tool,
    ToolDefinition,
    ToolParameter,
    ToolContext,
    ToolResult,
    ToolCategory,
)


class SetSavingsGoalTool(Tool):
    """Tool for creating or updating savings goals."""

    definition = ToolDefinition(
        name="set_savings_goal",
        display_name="Savings Goal Manager",
        category=ToolCategory.PLANNING,
        version="1.0.0",

        description="Create a new savings goal or update an existing one. Set target amounts, deadlines, and monthly contribution targets.",

        when_to_use="Use when the user wants to create a new savings goal, update an existing goal, or change their target. Examples: 'I want to save for a vacation', 'set a goal for $5000', 'create emergency fund goal'.",

        when_not_to_use="Do not use for adding money to a goal (use add_savings_contribution) or checking progress.",

        example_triggers=[
            "I want to save for a vacation",
            "create a savings goal",
            "set a goal for $5000",
            "start an emergency fund",
            "update my savings target",
            "save for a new laptop",
        ],

        parameters=[
            ToolParameter(
                name="name",
                type="string",
                description="Name of the savings goal",
                required=True,
                max_length=100
            ),
            ToolParameter(
                name="target_amount",
                type="number",
                description="Target amount to save in dollars",
                required=True,
                min_value=1
            ),
            ToolParameter(
                name="target_date",
                type="string",
                description="Target date to reach goal (YYYY-MM-DD format). Optional.",
                required=False
            ),
            ToolParameter(
                name="monthly_contribution",
                type="number",
                description="Planned monthly contribution amount",
                required=False,
                min_value=0
            ),
            ToolParameter(
                name="priority",
                type="integer",
                description="Priority level (1=high, 2=medium, 3=low)",
                required=False,
                default=2,
                min_value=1,
                max_value=3
            ),
            ToolParameter(
                name="description",
                type="string",
                description="Optional description of the goal",
                required=False
            ),
            ToolParameter(
                name="update_existing",
                type="boolean",
                description="If true, update existing goal with same name instead of creating new",
                required=False,
                default=True
            ),
        ],

        requires=["authenticated"],
        produces=["data:savings_goal"],
        side_effects=["creates_savings_goal", "updates_savings_goal"],
        confirmation_required=False,
        is_destructive=False,
        timeout_seconds=10,
        visual_type=None,
    )

    async def execute(self, context: ToolContext) -> ToolResult:
        """Execute the savings goal creation/update."""
        try:
            from db_models import db, SavingsGoal

            name = context.params.get("name")
            target_amount = context.params.get("target_amount")
            target_date_str = context.params.get("target_date")
            monthly_contribution = context.params.get("monthly_contribution")
            priority = context.params.get("priority", 2)
            description = context.params.get("description")
            update_existing = context.params.get("update_existing", True)

            # Parse target date
            target_date = None
            if target_date_str:
                try:
                    target_date = datetime.strptime(target_date_str, "%Y-%m-%d").date()
                except ValueError:
                    pass

            # Check for existing goal
            existing_goal = None
            if update_existing:
                existing_goal = SavingsGoal.query.filter_by(
                    user_id=context.user_id,
                    name=name,
                    is_active=True
                ).first()

            if existing_goal:
                # Update existing goal
                old_target = existing_goal.target_amount
                existing_goal.target_amount = target_amount
                if target_date:
                    existing_goal.target_date = target_date
                if monthly_contribution is not None:
                    existing_goal.monthly_contribution = monthly_contribution
                if description:
                    existing_goal.description = description
                existing_goal.priority = priority

                db.session.commit()

                progress = (existing_goal.current_amount / target_amount) * 100
                message = f"I've updated your '{name}' goal from ${old_target:,.2f} to ${target_amount:,.2f}."
                message += f" You're {progress:.1f}% of the way there with ${existing_goal.current_amount:,.2f} saved."

                goal = existing_goal
                is_new = False

            else:
                # Create new goal
                goal = SavingsGoal(
                    user_id=context.user_id,
                    name=name,
                    target_amount=target_amount,
                    current_amount=0,
                    target_date=target_date,
                    monthly_contribution=monthly_contribution or 0,
                    priority=priority,
                    description=description,
                    is_active=True
                )
                db.session.add(goal)
                db.session.commit()

                message = f"Great! I've created your '{name}' savings goal for ${target_amount:,.2f}."

                # Calculate suggested monthly contribution if not provided
                if not monthly_contribution and target_date:
                    months_until = self._months_between(date.today(), target_date)
                    if months_until > 0:
                        suggested = target_amount / months_until
                        message += f" To reach it by {target_date.strftime('%B %Y')}, you'd need to save about ${suggested:,.2f}/month."
                elif monthly_contribution:
                    months_needed = target_amount / monthly_contribution
                    projected_date = date.today() + relativedelta(months=int(months_needed))
                    message += f" At ${monthly_contribution:,.2f}/month, you'll reach this goal around {projected_date.strftime('%B %Y')}."

                is_new = True

            return ToolResult.success_result(
                data={
                    "goal_id": goal.id,
                    "name": name,
                    "target_amount": target_amount,
                    "current_amount": goal.current_amount,
                    "progress_percent": (goal.current_amount / target_amount) * 100,
                    "target_date": target_date.isoformat() if target_date else None,
                    "monthly_contribution": goal.monthly_contribution,
                    "is_new": is_new,
                },
                message=message,
                suggestions=[
                    "Add money to this goal",
                    "Show all my savings goals",
                    "How much should I save monthly?"
                ]
            )

        except Exception as e:
            return ToolResult.error_result(
                f"Failed to set savings goal: {str(e)}",
                "SAVINGS_GOAL_ERROR"
            )

    def _months_between(self, start: date, end: date) -> int:
        """Calculate months between two dates."""
        return (end.year - start.year) * 12 + (end.month - start.month)


class AddSavingsContributionTool(Tool):
    """Tool for adding contributions to savings goals."""

    definition = ToolDefinition(
        name="add_savings_contribution",
        display_name="Savings Contribution",
        category=ToolCategory.TRACKING,
        version="1.0.0",

        description="Add a contribution to an existing savings goal. Records the contribution and updates the goal's progress.",

        when_to_use="Use when the user wants to add money to a savings goal. Examples: 'add $100 to my emergency fund', 'put $50 toward vacation', 'contribute to my savings'.",

        when_not_to_use="Do not use for creating new goals (use set_savings_goal) or checking progress.",

        example_triggers=[
            "add $100 to my emergency fund",
            "put money toward my vacation goal",
            "contribute to savings",
            "I saved $50 for my laptop",
        ],

        parameters=[
            ToolParameter(
                name="goal_name",
                type="string",
                description="Name of the savings goal to contribute to",
                required=True
            ),
            ToolParameter(
                name="amount",
                type="number",
                description="Amount to contribute in dollars",
                required=True,
                min_value=0.01
            ),
            ToolParameter(
                name="notes",
                type="string",
                description="Optional notes about this contribution",
                required=False
            ),
        ],

        requires=["authenticated"],
        produces=["data:contribution_added"],
        side_effects=["creates_contribution", "updates_goal_progress"],
        confirmation_required=False,
        is_destructive=False,
        timeout_seconds=10,
        visual_type=None,
    )

    async def execute(self, context: ToolContext) -> ToolResult:
        """Execute the savings contribution."""
        try:
            from db_models import db, SavingsGoal, SavingsContribution

            goal_name = context.params.get("goal_name")
            amount = context.params.get("amount")
            notes = context.params.get("notes")

            # Find the goal
            goal = SavingsGoal.query.filter_by(
                user_id=context.user_id,
                is_active=True
            ).filter(
                SavingsGoal.name.ilike(f"%{goal_name}%")
            ).first()

            if not goal:
                # List available goals
                active_goals = SavingsGoal.query.filter_by(
                    user_id=context.user_id,
                    is_active=True
                ).all()

                if active_goals:
                    goal_names = ", ".join([g.name for g in active_goals])
                    return ToolResult.error_result(
                        f"I couldn't find a goal matching '{goal_name}'. Your active goals are: {goal_names}",
                        "GOAL_NOT_FOUND"
                    )
                else:
                    return ToolResult.error_result(
                        "You don't have any active savings goals. Would you like to create one?",
                        "NO_GOALS"
                    )

            # Create contribution record
            contribution = SavingsContribution(
                goal_id=goal.id,
                user_id=context.user_id,
                amount=amount,
                contribution_date=date.today(),
                source="manual",
                notes=notes
            )
            db.session.add(contribution)

            # Update goal progress
            old_amount = goal.current_amount
            goal.current_amount = old_amount + amount

            # Check if goal is completed
            if goal.current_amount >= goal.target_amount and not goal.is_completed:
                goal.is_completed = True
                goal.completed_at = datetime.utcnow()

            db.session.commit()

            progress = (goal.current_amount / goal.target_amount) * 100
            remaining = goal.target_amount - goal.current_amount

            # Build response message
            if goal.is_completed:
                message = f"Congratulations! You've completed your '{goal.name}' goal! "
                message += f"You saved a total of ${goal.current_amount:,.2f}!"
            else:
                message = f"Added ${amount:,.2f} to your '{goal.name}' goal! "
                message += f"You're now at ${goal.current_amount:,.2f} ({progress:.1f}% of ${goal.target_amount:,.2f}). "
                message += f"Only ${remaining:,.2f} to go!"

            return ToolResult.success_result(
                data={
                    "goal_id": goal.id,
                    "goal_name": goal.name,
                    "contribution_amount": amount,
                    "new_total": goal.current_amount,
                    "target": goal.target_amount,
                    "progress_percent": progress,
                    "remaining": remaining,
                    "is_completed": goal.is_completed,
                },
                message=message,
                suggestions=[
                    "Show my savings progress",
                    "How much more do I need?",
                    "Show all my goals"
                ]
            )

        except Exception as e:
            return ToolResult.error_result(
                f"Failed to add contribution: {str(e)}",
                "CONTRIBUTION_ERROR"
            )
