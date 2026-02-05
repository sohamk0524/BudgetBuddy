"""
Data models for BudgetBuddy backend.
Mirrors the Swift Codable structs expected by the iOS app.
"""

from dataclasses import dataclass, asdict
from typing import Optional, List, Dict, Any
import uuid


@dataclass
class SankeyNode:
    """A node in a Sankey flow diagram."""
    id: str
    name: str
    value: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "value": self.value
        }


@dataclass
class BurndownDataPoint:
    """A data point for burndown charts."""
    date: str  # ISO format date string
    amount: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "date": self.date,
            "amount": self.amount
        }


class VisualPayload:
    """
    Helper class to create visual payloads that match the iOS VisualComponent enum.
    The iOS app expects a 'type' discriminator field with associated data.
    """

    @staticmethod
    def burndown_chart(spent: float, budget: float, ideal_pace: float) -> Dict[str, Any]:
        """Create a burndown chart payload."""
        return {
            "type": "burndownChart",
            "spent": spent,
            "budget": budget,
            "idealPace": ideal_pace
        }

    @staticmethod
    def sankey_flow(nodes: List[SankeyNode]) -> Dict[str, Any]:
        """Create a sankey flow diagram payload."""
        return {
            "type": "sankeyFlow",
            "nodes": [node.to_dict() for node in nodes]
        }

    @staticmethod
    def interactive_slider(category: str, current: float, max_val: float) -> Dict[str, Any]:
        """Create an interactive slider payload."""
        return {
            "type": "interactiveSlider",
            "category": category,
            "current": current,
            "max": max_val
        }

    @staticmethod
    def budget_slider(category: str, current: float, max_val: float) -> Dict[str, Any]:
        """Create a budget slider payload."""
        return {
            "type": "budgetSlider",
            "category": category,
            "current": current,
            "max": max_val
        }

    # ==========================================================================
    # NEW VISUAL PAYLOAD TYPES (Phase 2)
    # ==========================================================================

    @staticmethod
    def comparison_chart(
        current_period: Dict[str, Any],
        previous_period: Dict[str, Any],
        categories: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Create a comparison chart showing current vs previous period spending.

        Args:
            current_period: Dict with 'label', 'total', 'start_date', 'end_date'
            previous_period: Dict with 'label', 'total', 'start_date', 'end_date'
            categories: Optional list of category comparisons with 'name', 'current', 'previous'
        """
        return {
            "type": "comparisonChart",
            "currentPeriod": {
                "label": current_period.get("label", "This Month"),
                "total": current_period.get("total", 0),
                "startDate": current_period.get("start_date"),
                "endDate": current_period.get("end_date"),
            },
            "previousPeriod": {
                "label": previous_period.get("label", "Last Month"),
                "total": previous_period.get("total", 0),
                "startDate": previous_period.get("start_date"),
                "endDate": previous_period.get("end_date"),
            },
            "categories": categories or [],
            "changePercent": (
                ((current_period.get("total", 0) - previous_period.get("total", 1)) /
                 previous_period.get("total", 1) * 100)
                if previous_period.get("total", 0) > 0 else 0
            )
        }

    @staticmethod
    def goal_progress(goals: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Create a goal progress visualization showing multiple savings goals.

        Args:
            goals: List of goal dicts with 'name', 'current', 'target', 'icon', 'color'
        """
        formatted_goals = []
        total_current = 0
        total_target = 0

        for goal in goals:
            current = goal.get("current", 0)
            target = goal.get("target", 1)
            total_current += current
            total_target += target

            formatted_goals.append({
                "name": goal.get("name", "Goal"),
                "current": current,
                "target": target,
                "progressPercent": round((current / target) * 100, 1) if target > 0 else 0,
                "remaining": max(0, target - current),
                "icon": goal.get("icon"),
                "color": goal.get("color"),
            })

        return {
            "type": "goalProgress",
            "goals": formatted_goals,
            "totalCurrent": total_current,
            "totalTarget": total_target,
            "overallProgress": round((total_current / total_target) * 100, 1) if total_target > 0 else 0
        }

    @staticmethod
    def transaction_list(
        transactions: List[Dict[str, Any]],
        filters: Optional[Dict[str, Any]] = None,
        summary: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a transaction list visualization.

        Args:
            transactions: List of transaction dicts with 'id', 'description', 'amount',
                         'category', 'date', 'merchant'
            filters: Optional filter state dict with 'category', 'dateRange', 'amountRange'
            summary: Optional summary dict with 'totalIncome', 'totalExpenses', 'count'
        """
        formatted_transactions = []
        for tx in transactions:
            amount = tx.get("amount", 0)
            formatted_transactions.append({
                "id": tx.get("id", str(uuid.uuid4())),
                "description": tx.get("description", ""),
                "amount": amount,
                "isExpense": amount < 0 or tx.get("transaction_type") == "expense",
                "category": tx.get("category", "other"),
                "date": tx.get("date"),
                "merchant": tx.get("merchant"),
                "icon": tx.get("icon"),
            })

        return {
            "type": "transactionList",
            "transactions": formatted_transactions,
            "filters": filters or {},
            "summary": summary or {
                "totalIncome": sum(t["amount"] for t in formatted_transactions if not t["isExpense"]),
                "totalExpenses": sum(abs(t["amount"]) for t in formatted_transactions if t["isExpense"]),
                "count": len(formatted_transactions),
            }
        }

    @staticmethod
    def action_card(
        title: str,
        message: str,
        actions: List[Dict[str, Any]],
        icon: Optional[str] = None,
        severity: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create an action card with buttons for user interaction.

        Args:
            title: Card title
            message: Card body message
            actions: List of action dicts with 'label', 'action', 'style' (primary/secondary/danger)
            icon: Optional icon name or emoji
            severity: Optional severity level ('info', 'warning', 'success', 'error')
        """
        formatted_actions = []
        for action in actions:
            formatted_actions.append({
                "label": action.get("label", ""),
                "action": action.get("action", ""),
                "style": action.get("style", "primary"),
                "data": action.get("data", {}),
            })

        return {
            "type": "actionCard",
            "title": title,
            "message": message,
            "actions": formatted_actions,
            "icon": icon,
            "severity": severity or "info",
        }

    @staticmethod
    def spending_plan(
        safe_to_spend: float,
        categories: List[Dict[str, Any]],
        summary: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a spending plan visualization.

        Args:
            safe_to_spend: Amount safe to spend after bills and savings
            categories: List of category allocations with 'name', 'budgeted', 'spent', 'icon'
            summary: Optional summary with 'totalIncome', 'totalBills', 'totalSavings'
        """
        formatted_categories = []
        for cat in categories:
            budgeted = cat.get("budgeted", 0)
            spent = cat.get("spent", 0)
            formatted_categories.append({
                "name": cat.get("name", ""),
                "budgeted": budgeted,
                "spent": spent,
                "remaining": max(0, budgeted - spent),
                "percentUsed": round((spent / budgeted) * 100, 1) if budgeted > 0 else 0,
                "icon": cat.get("icon"),
                "color": cat.get("color"),
            })

        return {
            "type": "spendingPlan",
            "safeToSpend": safe_to_spend,
            "categories": formatted_categories,
            "summary": summary or {}
        }

    @staticmethod
    def category_breakdown(
        categories: List[Dict[str, Any]],
        total: float
    ) -> Dict[str, Any]:
        """
        Create a category breakdown visualization (pie/donut chart data).

        Args:
            categories: List of categories with 'name', 'amount', 'color'
            total: Total amount for percentage calculations
        """
        formatted = []
        for cat in categories:
            amount = cat.get("amount", 0)
            formatted.append({
                "name": cat.get("name", "Other"),
                "amount": amount,
                "percent": round((amount / total) * 100, 1) if total > 0 else 0,
                "color": cat.get("color"),
            })

        return {
            "type": "categoryBreakdown",
            "categories": formatted,
            "total": total
        }

    @staticmethod
    def insight_card(
        title: str,
        insight: str,
        data_points: Optional[List[Dict[str, Any]]] = None,
        trend: Optional[str] = None,
        recommendation: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create an insight card for displaying financial insights.

        Args:
            title: Insight title
            insight: Main insight text
            data_points: Optional supporting data points
            trend: Optional trend indicator ('up', 'down', 'stable')
            recommendation: Optional recommended action
        """
        return {
            "type": "insightCard",
            "title": title,
            "insight": insight,
            "dataPoints": data_points or [],
            "trend": trend,
            "recommendation": recommendation,
        }


# =============================================================================
# ADDITIONAL DATA CLASSES
# =============================================================================

@dataclass
class GoalProgress:
    """Progress data for a savings goal."""
    name: str
    current: float
    target: float
    icon: Optional[str] = None
    color: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        progress = (self.current / self.target * 100) if self.target > 0 else 0
        return {
            "name": self.name,
            "current": self.current,
            "target": self.target,
            "progressPercent": round(progress, 1),
            "remaining": max(0, self.target - self.current),
            "icon": self.icon,
            "color": self.color,
        }


@dataclass
class CategoryAllocation:
    """Budget allocation for a category."""
    name: str
    budgeted: float
    spent: float = 0.0
    icon: Optional[str] = None
    color: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "budgeted": self.budgeted,
            "spent": self.spent,
            "remaining": max(0, self.budgeted - self.spent),
            "percentUsed": round((self.spent / self.budgeted * 100), 1) if self.budgeted > 0 else 0,
            "icon": self.icon,
            "color": self.color,
        }


@dataclass
class ActionButton:
    """An action button for action cards."""
    label: str
    action: str  # Action identifier
    style: str = "primary"  # "primary", "secondary", "danger"
    data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "label": self.label,
            "action": self.action,
            "style": self.style,
            "data": self.data or {},
        }


@dataclass
class AssistantResponse:
    """
    The response format expected by the iOS app.
    Uses camelCase for JSON serialization.
    """
    text_message: str
    visual_payload: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with camelCase keys for JSON serialization."""
        result = {
            "textMessage": self.text_message
        }
        if self.visual_payload is not None:
            result["visualPayload"] = self.visual_payload
        else:
            result["visualPayload"] = None
        return result
