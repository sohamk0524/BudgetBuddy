"""
Budget Overview Tool - Get user's budget breakdown with Sankey visualization.
"""

from tools.base import (
    Tool,
    ToolDefinition,
    ToolParameter,
    ToolContext,
    ToolResult,
    ToolCategory,
)
from models import VisualPayload, SankeyNode


class BudgetOverviewTool(Tool):
    """Tool for getting budget overview with Sankey flow visualization."""

    definition = ToolDefinition(
        name="get_budget_overview",
        display_name="Budget Overview",
        category=ToolCategory.ANALYSIS,
        version="2.0.0",

        description="Get the user's budget breakdown showing income and all expense categories as a flow diagram.",

        when_to_use="ONLY use when the user explicitly asks to see their budget, spending breakdown, monthly plan, or where their money goes. Examples: 'show my budget', 'where does my money go', 'spending breakdown'.",

        when_not_to_use="Do NOT use for greetings, general conversation, or questions that don't specifically ask about budget breakdown.",

        example_triggers=[
            "show my budget",
            "spending breakdown",
            "where does my money go",
            "show my monthly plan",
            "budget overview",
        ],

        parameters=[
            ToolParameter(
                name="month",
                type="string",
                description="Month to show budget for (YYYY-MM format). Defaults to current month.",
                required=False,
                default=None
            ),
            ToolParameter(
                name="include_savings",
                type="boolean",
                description="Whether to include savings in the breakdown.",
                required=False,
                default=True
            ),
        ],

        requires=["authenticated", "has_plan"],
        produces=["data:budget_breakdown", "visual:sankeyFlow"],
        side_effects=[],
        confirmation_required=False,
        is_destructive=False,
        timeout_seconds=10,
        visual_type="sankeyFlow",
    )

    async def execute(self, context: ToolContext) -> ToolResult:
        """Execute the budget overview retrieval."""
        from services.data_mock import get_budget_overview_data

        try:
            # Get budget data (will use real data when available)
            data = get_budget_overview_data()

            # Build Sankey nodes from the data
            nodes = [
                SankeyNode(
                    id=node["id"],
                    name=node["name"],
                    value=node["value"]
                )
                for node in data.get("nodes", [])
            ]

            # Create visual payload
            visual = VisualPayload.sankey_flow(nodes)

            # Build response message
            summary = data.get("summary", {})
            total_income = summary.get("total_income", 0)
            total_spent = summary.get("total_spent", 0)
            remaining = summary.get("remaining", 0)

            message = (
                f"Here's your budget breakdown. "
                f"Income: ${total_income:,.2f}, "
                f"Spent: ${total_spent:,.2f}, "
                f"Remaining: ${remaining:,.2f}."
            )

            return ToolResult.success_result(
                data={
                    "nodes": [node.to_dict() for node in nodes],
                    "summary": summary
                },
                message=message,
                visual=visual,
                suggestions=[
                    "Show me my spending status",
                    "Am I on track this month?",
                    "What category am I overspending in?"
                ]
            )

        except Exception as e:
            return ToolResult.error_result(
                f"Failed to retrieve budget overview: {str(e)}",
                "BUDGET_OVERVIEW_ERROR"
            )
