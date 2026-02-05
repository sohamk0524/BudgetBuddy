"""
Account Balance Tool - Get user's account balance information.
"""

from tools.base import (
    Tool,
    ToolDefinition,
    ToolParameter,
    ToolContext,
    ToolResult,
    ToolCategory,
)


class AccountBalanceTool(Tool):
    """Tool for retrieving account balance information."""

    definition = ToolDefinition(
        name="get_account_balance",
        display_name="Account Balance",
        category=ToolCategory.ACCOUNT_MANAGEMENT,
        version="2.0.0",

        description="Get the user's current account balance and available funds across all accounts.",

        when_to_use="ONLY use when the user asks about their balance, how much money they have, or available funds. Examples: 'what's my balance', 'how much do I have', 'available funds'.",

        when_not_to_use="Do NOT use for questions about budget status, spending breakdown, or savings goals.",

        example_triggers=[
            "what's my balance",
            "how much do I have",
            "available funds",
            "my account balance",
            "how much money do I have",
            "check my balance",
        ],

        parameters=[
            ToolParameter(
                name="account_type",
                type="string",
                description="Specific account type to check. If not provided, shows all accounts.",
                required=False,
                default=None,
                enum=["checking", "savings", "credit_card", "all"]
            ),
        ],

        requires=["authenticated"],
        produces=["data:account_balances"],
        side_effects=[],
        confirmation_required=False,
        is_destructive=False,
        timeout_seconds=10,
        visual_type=None,  # No visualization for account balance
    )

    async def execute(self, context: ToolContext) -> ToolResult:
        """Execute the account balance retrieval."""
        from services.data_mock import get_account_balance_data

        try:
            # Get account balance data
            data = get_account_balance_data()

            checking = data.get("checking_balance", 0)
            savings = data.get("savings_balance", 0)
            total_liquid = data.get("total_liquid", 0)
            credit_balance = data.get("credit_card_balance", 0)
            credit_available = data.get("credit_available", 0)
            net_worth = data.get("net_worth", 0)

            # Filter by account type if specified
            account_type = context.params.get("account_type")

            if account_type == "checking":
                message = f"Your checking account balance is ${checking:,.2f}."
                filtered_data = {"checking_balance": checking}
            elif account_type == "savings":
                message = f"Your savings account balance is ${savings:,.2f}."
                filtered_data = {"savings_balance": savings}
            elif account_type == "credit_card":
                message = (
                    f"Your credit card balance is ${credit_balance:,.2f}. "
                    f"You have ${credit_available:,.2f} available credit."
                )
                filtered_data = {
                    "credit_card_balance": credit_balance,
                    "credit_available": credit_available
                }
            else:
                # Show all accounts
                message = (
                    f"Here's your account summary:\n"
                    f"- Checking: ${checking:,.2f}\n"
                    f"- Savings: ${savings:,.2f}\n"
                    f"- Total liquid: ${total_liquid:,.2f}\n"
                    f"- Credit card balance: ${credit_balance:,.2f}\n"
                    f"- Net worth: ${net_worth:,.2f}"
                )
                filtered_data = data

            return ToolResult.success_result(
                data=filtered_data,
                message=message,
                visual=None,
                suggestions=[
                    "Show my savings progress",
                    "Am I on track with my budget?",
                    "Show my budget breakdown"
                ]
            )

        except Exception as e:
            return ToolResult.error_result(
                f"Failed to retrieve account balance: {str(e)}",
                "ACCOUNT_BALANCE_ERROR"
            )
