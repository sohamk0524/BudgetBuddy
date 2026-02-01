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
