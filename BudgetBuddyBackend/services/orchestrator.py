"""
Orchestrator service - The "Brain" of BudgetBuddy.
Uses a declarative Agent with LiteLLM for intelligent conversation and tool calling.
"""

from typing import Optional, Dict, Any
from models import AssistantResponse, VisualPayload, SankeyNode
from services.llm_service import Agent
from services.tools import get_tools, execute_tool, set_tool_context
from services.data_mock import get_spending_status_data


def get_user_profile(user_id):
    """
    Fetch user's financial profile from the database.
    Returns None if user or profile doesn't exist.
    """
    try:
        from db_models import get_user, get_profile
        user_id_int = int(user_id)
        user = get_user(user_id_int)
        if user:
            profile = get_profile(user_id_int)
            if profile:
                return {
                    "is_student": profile.get('is_student'),
                    "budgeting_goal": profile.get('budgeting_goal'),
                    "strictness_level": profile.get('strictness_level'),
                    "savings_goal_name": profile.get('savings_goal_name'),
                    "savings_goal_target": profile.get('savings_goal_target'),
                }
    except Exception:
        pass
    return None


# System prompt that guides conversation and tool usage
SYSTEM_PROMPT = """You are BudgetBuddy, a friendly AI financial assistant. You help users understand their finances, track spending, and make smart money decisions.

CONVERSATION GUIDELINES:
- Be warm, helpful, and conversational
- Keep responses concise (2-4 sentences for simple questions)
- For greetings like "hi", "hello", "hey" - just respond naturally and friendly, do NOT use any tools
- For general questions like "what can you do?" - explain your capabilities without using tools

AVAILABLE TOOLS AND WHEN TO USE THEM:

1. get_plaid_transactions - Use when user asks about:
   - Their recent spending, transactions, or purchases
   - Where their money is going
   - Spending patterns or habits

2. get_financial_summary - Use when user asks about:
   - Their balance or net worth
   - How much money they have
   - Safe-to-spend amount
   - Overall financial health

3. get_spending_status - Use for budget tracking status
4. get_savings_progress - Use for savings goal progress

5. render_visual - Render a chart or diagram for the user
   - ONLY call this when you have REAL data that would benefit from visualization
   - Do NOT render visuals for greetings, errors, or when the user has no data
   - Types: "spending_plan" (budget categories), "burndown_chart" (spending pace), "sankey_flow" (money flow)
   - For spending_plan, pass: {"safe_to_spend": <number>, "categories": <array from get_budget_plan>}
   - For burndown_chart, pass: {"spent": <number>, "budget": <number>, "ideal_pace": <number>}
   - For sankey_flow, pass: {"nodes": [{"id": "...", "name": "...", "value": <number>}]}

IMPORTANT GUIDANCE:
- When user asks for help reducing spending or financial advice, fetch their transactions with get_plaid_transactions
- You can call multiple tools if needed to give comprehensive advice
- If a tool returns "has_plaid: false", let the user know they need to link their bank account first
- Only call render_visual when you have real data to show — never for missing data or error states

DO NOT USE TOOLS FOR:
- Greetings (hi, hello, hey, good morning, etc.)
- General questions (how are you, what can you do)
- Non-financial topics
- When the user is just chatting

RESPONSE STYLE:
- Be encouraging but honest about their financial situation
- When you use a tool, explain the data in simple, actionable terms
- Use specific numbers from the tool results
- Give concrete, personalized advice based on their actual data"""


# Initialize the agent
agent = Agent(
    name="BudgetBuddy",
    instructions=SYSTEM_PROMPT,
    tools=get_tools(),
    model="claude-opus-4-6",
    tool_executor=execute_tool,
)


def _build_user_context(user_id_int: Optional[int]) -> Optional[str]:
    """
    Build a detailed context string about the user for the LLM.
    Pre-fetches key financial data so the agent starts every conversation
    with a complete picture of the user's state.
    """
    if not user_id_int:
        return None

    try:
        from db_models import (
            get_user, get_profile, get_latest_plan,
            get_statement, get_active_plaid_items, get_accounts_for_item,
        )
        import json

        user = get_user(user_id_int)
        if not user:
            return None

        context_parts = []

        # Profile info
        profile = get_profile(user_id_int)
        if profile:
            goal = (profile.get('budgeting_goal') or "").replace("_", " ").title()
            context_parts.append(f"- Financial profile: goal={goal}, strictness={profile.get('strictness_level')}, student={profile.get('is_student')}")
        else:
            context_parts.append("- No financial profile (user has NOT completed onboarding)")

        # Budget plan summary
        plan = get_latest_plan(user_id_int)
        if plan:
            try:
                plan_data = json.loads(plan['plan_json'])
                safe_to_spend = plan_data.get("safeToSpend", 0)
                categories = plan_data.get("categoryAllocations", plan_data.get("categories", []))
                total_budget = sum(c.get("amount", 0) for c in categories)
                cat_names = [c.get("name", "") for c in categories]
                context_parts.append(
                    f"- Has budget plan: safe_to_spend=${safe_to_spend:.2f}, "
                    f"total_budget=${total_budget:.2f}, categories=[{', '.join(cat_names)}]"
                )
            except (json.JSONDecodeError, TypeError):
                context_parts.append("- Has a budget plan (use get_budget_plan for details)")
        else:
            context_parts.append("- No budget plan created yet")

        # Bank statement summary
        statement = get_statement(user_id_int)
        if statement:
            context_parts.append(
                f"- Has bank statement: income=${statement.get('total_income', 0):.2f}, "
                f"expenses=${statement.get('total_expenses', 0):.2f}, balance=${statement.get('ending_balance', 0):.2f}"
            )
        else:
            context_parts.append("- No bank statement uploaded")

        # Plaid connection status
        plaid_items = get_active_plaid_items(user_id_int)
        if plaid_items:
            account_count = sum(len(get_accounts_for_item(item.key.id)) for item in plaid_items)
            institution_names = [item.get('institution_name') or "Unknown" for item in plaid_items]
            context_parts.append(
                f"- Plaid linked: {account_count} account(s) at {', '.join(institution_names)}"
            )
        else:
            context_parts.append("- No bank accounts linked via Plaid")

        if context_parts:
            return "\n".join(context_parts)

    except Exception:
        pass

    return None


def process_message(text: str, user_id: str = "default") -> AssistantResponse:
    """
    Process user message using the AI agent with tool calling.

    Args:
        text: The user's input message
        user_id: Optional user identifier for context

    Returns:
        AssistantResponse with text and optional visual payload
    """
    # Convert user_id to int if possible (for database lookups)
    user_id_int = None
    try:
        user_id_int = int(user_id)
    except (ValueError, TypeError):
        pass

    # Set tool context so tools can access user data
    set_tool_context(user_id_int)

    try:
        # Check if the LLM provider is available
        if not agent.is_available():
            return _fallback_response(
                text,
                "I'm having trouble connecting to my AI backend. Please try again in a moment."
            )

        # Build user context and append to the message
        context_info = _build_user_context(user_id_int)
        user_message = text
        if context_info:
            user_message = f"{text}\n\n[USER CONTEXT:\n{context_info}]"

        # Run the agent — it decides whether to use tools
        result = agent.run(user_message)

        # Extract the response
        response_text = result.get("content", "I'm not sure how to help with that. Try asking about your budget or spending!")
        tool_results = result.get("tool_results", [])

        # Extract visual payload if the agent called render_visual
        visual_payload = _extract_visual_payload(tool_results)

        return AssistantResponse(
            text_message=response_text,
            visual_payload=visual_payload
        )

    except Exception as e:
        print(f"Orchestrator error: {e}")
        return _fallback_response(text)


def _extract_visual_payload(tool_results: list) -> Optional[Dict[str, Any]]:
    """
    Extract visual payload from the agent's render_visual tool call.
    Returns None if the agent didn't render a visual.
    """
    if not tool_results:
        return None

    for tool_result in tool_results:
        if tool_result.get("tool") != "render_visual":
            continue

        result_data = tool_result.get("result", {})
        if not result_data.get("rendered"):
            continue

        visual_type = result_data.get("visual_type")
        data = result_data.get("data", {})

        if visual_type == "spending_plan":
            return VisualPayload.spending_plan(
                safe_to_spend=data.get("safe_to_spend", 0),
                categories=data.get("categories", [])
            )
        elif visual_type == "burndown_chart":
            return VisualPayload.burndown_chart(
                spent=data.get("spent", 0),
                budget=data.get("budget", 0),
                ideal_pace=data.get("ideal_pace", 0)
            )
        elif visual_type == "sankey_flow":
            nodes = data.get("nodes", [])
            return VisualPayload.sankey_flow([
                SankeyNode(
                    id=node.get("id", ""),
                    name=node.get("name", ""),
                    value=node.get("value", 0)
                )
                for node in nodes
            ])

    return None


def _fallback_response(text: str, error_message: str = None) -> AssistantResponse:
    """
    Provide a fallback response when the AI is unavailable.
    """
    if error_message:
        return AssistantResponse(
            text_message=error_message,
            visual_payload=None
        )

    # Simple fallback for when AI is down
    text_lower = text.lower()

    if any(word in text_lower for word in ["hi", "hello", "hey"]):
        return AssistantResponse(
            text_message="Hey there! I'm BudgetBuddy. I'm having some technical difficulties, but I'm here to help with your finances!",
            visual_payload=None
        )

    if any(keyword in text_lower for keyword in ["afford", "status", "overspending"]):
        data = get_spending_status_data()
        return AssistantResponse(
            text_message=f"You've spent ${data['spent']:,.2f} of your ${data['budget']:,.2f} budget. (AI temporarily unavailable)",
            visual_payload=VisualPayload.burndown_chart(
                spent=data["spent"],
                budget=data["budget"],
                ideal_pace=data["idealPace"]
            )
        )

    return AssistantResponse(
        text_message="I'm having some technical difficulties. Try asking about your budget or spending status!",
        visual_payload=None
    )
