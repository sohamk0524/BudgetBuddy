"""
Orchestrator service - The "Brain" of BudgetBuddy.
Analyzes user input and decides whether to return a simple text response
or a complex visual payload.
"""

from models import AssistantResponse, VisualPayload
from services.data_mock import get_sankey_flow_nodes, get_burndown_data


def process_message(text: str) -> AssistantResponse:
    """
    Process user message and return appropriate response.
    Uses keyword detection for the prototype.

    Args:
        text: The user's input message

    Returns:
        AssistantResponse with text and optional visual payload
    """
    text_lower = text.lower()

    # Case A: The Plan - User wants to see budget flow/overview
    if any(keyword in text_lower for keyword in ["plan", "overview", "flow"]):
        nodes = get_sankey_flow_nodes()
        visual = VisualPayload.sankey_flow(nodes)
        return AssistantResponse(
            text_message="Here is your flow for Novasdfember.",
            visual_payload=visual
        )

    # Case B: Spending Check - User wants to check if they can afford something
    if any(keyword in text_lower for keyword in ["afford", "can i buy", "status", "spending"]):
        burndown = get_burndown_data()
        visual = VisualPayload.burndown_chart(
            spent=burndown["spent"],
            budget=burndown["budget"],
            ideal_pace=burndown["ideal_pace"]
        )
        return AssistantResponse(
            text_message="That purchase is risky. You are pacing above budget.",
            visual_payload=visual
        )

    # Case C: Default - Guide user to available features
    return AssistantResponse(
        text_message="I can help you with that. Try asking to see your 'Plan' or checking your 'Status'.",
        visual_payload=None
    )
