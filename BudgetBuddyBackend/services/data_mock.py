"""
Mock data service for BudgetBuddy.
Provides hardcoded data values and colors for the prototype.
"""

import uuid
from typing import List
from models import SankeyNode


# Design System Colors
class Colors:
    TEAL = "#2DD4BF"
    PURPLE = "#A855F7"
    CORAL = "#F43F5E"
    SLATE = "#1E293B"


def get_sankey_flow_nodes() -> List[SankeyNode]:
    """
    Returns mock Sankey flow data for a monthly budget overview.
    Income: 5000, Expenses: Rent 2000, Food 800, Savings 1000
    """
    return [
        SankeyNode(id=str(uuid.uuid4()), name="Income", value=5000.0),
        SankeyNode(id=str(uuid.uuid4()), name="Rent", value=2000.0),
        SankeyNode(id=str(uuid.uuid4()), name="Food", value=800.0),
        SankeyNode(id=str(uuid.uuid4()), name="Savings", value=1000.0),
        SankeyNode(id=str(uuid.uuid4()), name="Utilities", value=400.0),
        SankeyNode(id=str(uuid.uuid4()), name="Entertainment", value=300.0),
        SankeyNode(id=str(uuid.uuid4()), name="Other", value=500.0),
    ]


def get_burndown_data() -> dict:
    """
    Returns mock burndown chart data for spending status.
    """
    return {
        "spent": 1200.0,
        "budget": 2000.0,
        "ideal_pace": 1000.0
    }


def get_overspending_burndown_data() -> dict:
    """
    Returns mock burndown chart data indicating overspending.
    """
    return {
        "spent": 1250.0,
        "budget": 2000.0,
        "ideal_pace": 900.0
    }
