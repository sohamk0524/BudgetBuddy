"""
Track Transaction Tool - Manually log expenses and income.
"""

from datetime import datetime, date
from typing import Optional

from tools.base import (
    Tool,
    ToolDefinition,
    ToolParameter,
    ToolContext,
    ToolResult,
    ToolCategory,
)


class TrackTransactionTool(Tool):
    """Tool for manually logging financial transactions."""

    definition = ToolDefinition(
        name="track_transaction",
        display_name="Transaction Tracker",
        category=ToolCategory.TRACKING,
        version="1.0.0",

        description="Manually log a financial transaction (expense or income) to track spending.",

        when_to_use="Use when the user wants to record a purchase, expense, or income they made. Examples: 'I just spent $50 on groceries', 'log a $20 expense', 'I got paid $500'.",

        when_not_to_use="Do not use for viewing transactions, checking balances, or analyzing spending patterns.",

        example_triggers=[
            "I spent $50 on groceries",
            "log an expense",
            "I bought coffee for $5",
            "record a transaction",
            "I got paid",
            "add income of $1000",
        ],

        parameters=[
            ToolParameter(
                name="amount",
                type="number",
                description="Transaction amount in dollars (positive number)",
                required=True,
                min_value=0.01
            ),
            ToolParameter(
                name="category",
                type="string",
                description="Spending category",
                required=True,
                enum=[
                    "groceries", "dining", "transportation", "utilities",
                    "entertainment", "shopping", "healthcare", "subscriptions",
                    "rent", "income", "savings", "other"
                ]
            ),
            ToolParameter(
                name="transaction_type",
                type="string",
                description="Whether this is an expense or income",
                required=False,
                default="expense",
                enum=["expense", "income"]
            ),
            ToolParameter(
                name="merchant",
                type="string",
                description="Where the transaction occurred (store, company, etc.)",
                required=False
            ),
            ToolParameter(
                name="transaction_date",
                type="string",
                description="Date of transaction in YYYY-MM-DD format. Defaults to today.",
                required=False
            ),
            ToolParameter(
                name="notes",
                type="string",
                description="Optional notes about the transaction",
                required=False
            ),
        ],

        requires=["authenticated"],
        produces=["data:transaction_logged"],
        side_effects=["creates_transaction", "updates_spending_totals"],
        confirmation_required=False,
        is_destructive=False,
        timeout_seconds=10,
        visual_type=None,
    )

    async def execute(self, context: ToolContext) -> ToolResult:
        """Execute the transaction tracking."""
        try:
            from db_models import db, Transaction, BudgetCategory

            # Extract parameters
            amount = context.params.get("amount")
            category = context.params.get("category")
            transaction_type = context.params.get("transaction_type", "expense")
            merchant = context.params.get("merchant")
            notes = context.params.get("notes")

            # Parse date
            date_str = context.params.get("transaction_date")
            if date_str:
                try:
                    transaction_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                except ValueError:
                    transaction_date = date.today()
            else:
                transaction_date = date.today()

            # Create transaction record
            transaction = Transaction(
                user_id=context.user_id,
                amount=amount,
                transaction_type=transaction_type,
                category=category,
                merchant=merchant,
                description=notes,
                transaction_date=transaction_date,
                source="manual"
            )

            db.session.add(transaction)

            # Update budget category spent amount if it exists
            current_month = datetime.now().strftime("%Y-%m")
            budget_category = BudgetCategory.query.filter_by(
                user_id=context.user_id,
                name=category,
                month_year=current_month
            ).first()

            if budget_category and transaction_type == "expense":
                budget_category.spent_amount = (budget_category.spent_amount or 0) + amount

            db.session.commit()

            # Build response message
            if transaction_type == "expense":
                message = f"Got it! I've logged your ${amount:,.2f} {category} expense"
                if merchant:
                    message += f" at {merchant}"
                message += "."

                # Add budget context if available
                if budget_category:
                    remaining = budget_category.budgeted_amount - budget_category.spent_amount
                    if remaining > 0:
                        message += f" You have ${remaining:,.2f} left in your {category} budget this month."
                    else:
                        message += f" Note: You're now ${abs(remaining):,.2f} over your {category} budget."
            else:
                message = f"Great! I've recorded ${amount:,.2f} income in the {category} category."

            return ToolResult.success_result(
                data={
                    "transaction_id": transaction.id,
                    "amount": amount,
                    "category": category,
                    "transaction_type": transaction_type,
                    "merchant": merchant,
                    "date": transaction_date.isoformat(),
                },
                message=message,
                suggestions=[
                    "Show my spending status",
                    "How much have I spent this month?",
                    "Show my budget breakdown"
                ]
            )

        except Exception as e:
            return ToolResult.error_result(
                f"Failed to log transaction: {str(e)}",
                "TRANSACTION_LOG_ERROR"
            )
