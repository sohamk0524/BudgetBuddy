"""
Update Budget Tool - Adjust budget allocations for categories.
"""

from datetime import datetime

from tools.base import (
    Tool,
    ToolDefinition,
    ToolParameter,
    ToolContext,
    ToolResult,
    ToolCategory,
)


class UpdateBudgetCategoryTool(Tool):
    """Tool for adjusting budget allocations."""

    definition = ToolDefinition(
        name="update_budget_category",
        display_name="Budget Adjuster",
        category=ToolCategory.PLANNING,
        version="1.0.0",

        description="Adjust the budget allocation for a spending category. Can increase or decrease the budgeted amount.",

        when_to_use="Use when the user wants to change how much they've budgeted for a category. Examples: 'increase my food budget', 'set dining budget to $300', 'reduce entertainment spending'.",

        when_not_to_use="Do not use for tracking actual expenses (use track_transaction) or viewing current budgets.",

        example_triggers=[
            "increase my groceries budget",
            "set dining budget to $300",
            "reduce my entertainment budget",
            "change my shopping allocation",
            "adjust my budget",
        ],

        parameters=[
            ToolParameter(
                name="category",
                type="string",
                description="The budget category to adjust",
                required=True,
                enum=[
                    "groceries", "dining", "transportation", "utilities",
                    "entertainment", "shopping", "healthcare", "subscriptions",
                    "rent", "savings", "other"
                ]
            ),
            ToolParameter(
                name="new_amount",
                type="number",
                description="The new budget amount for this category (if setting absolute value)",
                required=False,
                min_value=0
            ),
            ToolParameter(
                name="adjustment",
                type="number",
                description="Amount to increase (+) or decrease (-) the current budget by",
                required=False
            ),
            ToolParameter(
                name="is_essential",
                type="boolean",
                description="Whether this is an essential expense category",
                required=False
            ),
        ],

        requires=["authenticated"],
        produces=["data:budget_updated"],
        side_effects=["updates_budget_plan"],
        confirmation_required=True,
        is_destructive=False,
        timeout_seconds=10,
        visual_type=None,
    )

    async def execute(self, context: ToolContext) -> ToolResult:
        """Execute the budget update."""
        try:
            from db_models import db, BudgetCategory

            category = context.params.get("category")
            new_amount = context.params.get("new_amount")
            adjustment = context.params.get("adjustment")
            is_essential = context.params.get("is_essential")

            if new_amount is None and adjustment is None:
                return ToolResult.error_result(
                    "Please specify either a new amount or an adjustment value.",
                    "MISSING_AMOUNT"
                )

            current_month = datetime.now().strftime("%Y-%m")

            # Find or create budget category
            budget_category = BudgetCategory.query.filter_by(
                user_id=context.user_id,
                name=category,
                month_year=current_month
            ).first()

            old_amount = 0

            if budget_category:
                old_amount = budget_category.budgeted_amount or 0

                # Apply update
                if new_amount is not None:
                    budget_category.budgeted_amount = new_amount
                elif adjustment is not None:
                    budget_category.budgeted_amount = max(0, old_amount + adjustment)

                if is_essential is not None:
                    budget_category.is_essential = is_essential

            else:
                # Create new category
                if new_amount is None:
                    new_amount = max(0, adjustment) if adjustment else 0

                budget_category = BudgetCategory(
                    user_id=context.user_id,
                    name=category,
                    budgeted_amount=new_amount,
                    spent_amount=0,
                    month_year=current_month,
                    is_essential=is_essential or False
                )
                db.session.add(budget_category)

            db.session.commit()

            final_amount = budget_category.budgeted_amount
            spent = budget_category.spent_amount or 0
            remaining = final_amount - spent

            # Build response message
            if old_amount > 0:
                change = final_amount - old_amount
                if change > 0:
                    message = f"I've increased your {category} budget from ${old_amount:,.2f} to ${final_amount:,.2f}."
                elif change < 0:
                    message = f"I've decreased your {category} budget from ${old_amount:,.2f} to ${final_amount:,.2f}."
                else:
                    message = f"Your {category} budget is already set to ${final_amount:,.2f}."
            else:
                message = f"I've set your {category} budget to ${final_amount:,.2f} for this month."

            if spent > 0:
                message += f" You've spent ${spent:,.2f} so far, leaving ${remaining:,.2f} available."

            return ToolResult.success_result(
                data={
                    "category": category,
                    "old_amount": old_amount,
                    "new_amount": final_amount,
                    "spent": spent,
                    "remaining": remaining,
                    "month": current_month,
                },
                message=message,
                suggestions=[
                    "Show my budget breakdown",
                    "How am I doing overall?",
                    "What other categories should I adjust?"
                ]
            )

        except Exception as e:
            return ToolResult.error_result(
                f"Failed to update budget: {str(e)}",
                "BUDGET_UPDATE_ERROR"
            )
