"""
Orchestrator service - The "Brain" of BudgetBuddy.
Uses OpenAI SDK with Ollama for intelligent conversation and tool calling.
"""

import re
from typing import Optional, Dict, Any
from models import AssistantResponse, VisualPayload, SankeyNode
from services.llm_service import BudgetBuddyAgent, OllamaConnectionError, OllamaError
from services.tools import get_tool_definitions, execute_tool, set_tool_context
from services.data_mock import get_budget_overview_data, get_spending_status_data


def get_user_profile(user_id):
    """
    Fetch user's financial profile from the database.
    Returns None if user or profile doesn't exist.
    """
    try:
        from db_models import User
        user = User.query.get(user_id)
        if user and user.profile:
            return {
                "monthly_income": user.profile.monthly_income,
                "fixed_expenses": user.profile.fixed_expenses,
                "discretionary": user.profile.monthly_income - user.profile.fixed_expenses,
                "savings_goal_name": user.profile.savings_goal_name,
                "savings_goal_target": user.profile.savings_goal_target
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

1. get_budget_plan - Use when user asks about:
   - Their budget plan or spending plan
   - How to reduce spending or save money
   - What they should spend on different categories
   - Budget recommendations or advice
   - Their financial plan

2. get_spending_analysis - Use when user asks about:
   - Their actual spending habits
   - Where their money is going (from bank statement)
   - Top spending categories
   - Comparing actual vs planned spending

3. get_financial_summary - Use when user asks about:
   - Their balance or net worth
   - How much money they have
   - Safe-to-spend amount
   - Overall financial health

4. get_budget_overview - Use for quick budget overviews
5. get_spending_status - Use for budget tracking status
6. get_savings_progress - Use for savings goal progress

IMPORTANT GUIDANCE:
- When user asks for help reducing spending or financial advice, FIRST fetch their plan with get_budget_plan
- If they ask about actual spending, use get_spending_analysis
- You can call multiple tools if needed to give comprehensive advice
- If a tool returns "has_plan: false" or "has_statement: false", let the user know they need to set that up first

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
agent = BudgetBuddyAgent(model="llama3.2:3b")


def _should_use_tools(text: str) -> bool:
    """
    Determine if the message is likely asking about financial data.
    Only provide tools for finance-related queries to prevent over-eager tool calling.
    """
    text_lower = text.lower()

    # Keywords that suggest user wants financial data or advice
    finance_keywords = [
        # Budget and spending
        "budget", "spend", "spending", "expense", "expenses", "money",
        "afford", "cost", "balance", "account", "savings", "save",
        "income", "salary", "pay", "payment", "bill", "bills",
        "overview", "breakdown", "status", "track", "tracking",
        # Questions and help
        "how much", "how am i", "can i buy", "should i buy",
        "financial", "finances", "cash", "funds", "dollars", "$",
        # Advice and planning
        "reduce", "cut", "lower", "plan", "advice", "recommend",
        "help me", "tips", "suggest", "improve", "optimize",
        # Analysis
        "analyze", "analysis", "review", "where", "why",
        "category", "categories", "breakdown"
    ]

    return any(keyword in text_lower for keyword in finance_keywords)


def _extract_amount(text: str) -> float:
    """Extract a dollar amount from text, default to 100 if not found."""
    match = re.search(r'\$?([\d,]+(?:\.\d{2})?)', text)
    if match:
        return float(match.group(1).replace(',', ''))
    return 100.0


def _handle_personalized_query(text: str, user_id) -> Optional[AssistantResponse]:
    """
    Handle queries that require user's financial profile.
    Returns None if no personalized response is needed.
    """
    text_lower = text.lower()
    profile = get_user_profile(user_id)

    if not profile:
        return None

    discretionary = profile["discretionary"]

    # Handle "afford" or "can I buy" queries
    if "afford" in text_lower or "can i buy" in text_lower:
        amount = _extract_amount(text)

        if amount <= discretionary:
            response_text = f"Based on your budget, you have ${discretionary:,.2f} discretionary income. You can afford this ${amount:,.2f} purchase!"
        else:
            response_text = f"Your discretionary budget is ${discretionary:,.2f}. A ${amount:,.2f} purchase would exceed your available funds."

        return AssistantResponse(
            text_message=response_text,
            visual_payload=VisualPayload.burndown_chart(
                spent=amount,
                budget=discretionary,
                ideal_pace=discretionary * 0.5
            )
        )

    # Handle "plan" queries
    if "plan" in text_lower:
        income = profile["monthly_income"]
        expenses = profile["fixed_expenses"]

        nodes = [
            SankeyNode(id="income", name="Income", value=income),
            SankeyNode(id="expenses", name="Fixed Expenses", value=expenses),
            SankeyNode(id="discretionary", name="Discretionary", value=discretionary),
        ]

        if profile["savings_goal_name"]:
            nodes.append(SankeyNode(
                id="savings",
                name=profile["savings_goal_name"],
                value=profile["savings_goal_target"]
            ))

        return AssistantResponse(
            text_message=f"Here's your financial plan. You earn ${income:,.2f}/month with ${expenses:,.2f} in fixed expenses, leaving ${discretionary:,.2f} for spending and savings.",
            visual_payload=VisualPayload.sankey_flow(nodes)
        )

    return None


def _build_user_context(user_id_int: Optional[int]) -> Optional[str]:
    """
    Build a brief context string about the user for the LLM.
    This helps the LLM understand what data is available.
    """
    if not user_id_int:
        return None

    try:
        from db_models import User, BudgetPlan, SavedStatement

        user = User.query.get(user_id_int)
        if not user:
            return None

        context_parts = []

        # Check for profile
        if user.profile:
            context_parts.append(f"- User has a financial profile (income: ${user.profile.monthly_income:.2f}/month)")

        # Check for budget plan
        plan = BudgetPlan.query.filter_by(user_id=user_id_int).first()
        if plan:
            context_parts.append("- User has a budget plan (use get_budget_plan to access)")
        else:
            context_parts.append("- User does NOT have a budget plan yet")

        # Check for statement
        statement = SavedStatement.query.filter_by(user_id=user_id_int).first()
        if statement:
            context_parts.append("- User has uploaded a bank statement (use get_spending_analysis to access)")
        else:
            context_parts.append("- User has NOT uploaded a bank statement")

        if context_parts:
            return "\n".join(context_parts)

    except Exception:
        pass

    return None


def process_message(text: str, user_id: str = "default") -> AssistantResponse:
    """
    Process user message using the AI agent with optional tool calling.

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

    # Try personalized response first if user has a profile
    personalized = _handle_personalized_query(text, user_id)
    if personalized:
        return personalized

    try:
        # Check if Ollama is available
        if not agent.is_available():
            return _fallback_response(
                text,
                "I'm having trouble connecting to my AI backend. Please make sure Ollama is running with 'ollama serve'."
            )

        # Build the conversation with user context
        context_info = _build_user_context(user_id_int)
        system_prompt_with_context = SYSTEM_PROMPT
        if context_info:
            system_prompt_with_context += f"\n\nUSER CONTEXT:\n{context_info}"

        messages = [
            {"role": "system", "content": system_prompt_with_context},
            {"role": "user", "content": text}
        ]

        # Only provide tools if message seems finance-related
        # This prevents the model from over-eagerly calling tools for simple greetings
        use_tools = _should_use_tools(text)
        tools = get_tool_definitions() if use_tools else None

        # Call the agent
        if use_tools:
            result = agent.chat_with_tools(
                messages=messages,
                tools=tools,
                tool_executor=execute_tool,
                max_iterations=3
            )
        else:
            # Simple chat without tools for greetings/general questions
            response = agent.chat(messages, tools=None)
            result = {
                "content": response.choices[0].message.content or "",
                "tool_results": []
            }

        # Extract the response content
        response_text = result.get("content", "I'm not sure how to help with that. Try asking about your budget or spending!")
        tool_results = result.get("tool_results", [])

        # Determine visual payload based on tools called
        visual_payload = _determine_visual_payload(tool_results)

        return AssistantResponse(
            text_message=response_text,
            visual_payload=visual_payload
        )

    except OllamaConnectionError:
        return _fallback_response(
            text,
            "I can't connect to my AI backend right now. Please make sure Ollama is running."
        )
    except OllamaError as e:
        return _fallback_response(
            text,
            "I encountered an error processing your request. Please try again."
        )
    except Exception as e:
        print(f"Orchestrator error: {e}")
        return _fallback_response(text)


def _determine_visual_payload(tool_results: list) -> Optional[Dict[str, Any]]:
    """
    Determine the appropriate visual payload based on which tools were called.
    Returns None if no tools were called (for regular conversation).
    """
    if not tool_results:
        return None

    # Find the most relevant tool result for visualization
    for tool_result in tool_results:
        tool_name = tool_result.get("tool", "")
        result_data = tool_result.get("result", {})

        # Handle budget plan - show spending plan widget if categories exist
        if tool_name == "get_budget_plan":
            if result_data.get("has_plan") and result_data.get("categories"):
                categories = result_data.get("categories", [])
                safe_to_spend = result_data.get("safe_to_spend", 0)
                return VisualPayload.spending_plan(safe_to_spend, categories)

        # Handle spending analysis - show burndown of actual vs expected
        elif tool_name == "get_spending_analysis":
            if result_data.get("has_statement"):
                total_expenses = result_data.get("total_expenses", 0)
                total_income = result_data.get("total_income", 0)
                # Show a burndown comparing expenses to income
                return VisualPayload.burndown_chart(
                    spent=total_expenses,
                    budget=total_income,
                    ideal_pace=total_income * 0.7  # Assume 70% spending is ideal
                )

        # Handle financial summary - show burndown of safe to spend
        elif tool_name == "get_financial_summary":
            safe_to_spend = result_data.get("safe_to_spend", 0)
            net_worth = result_data.get("net_worth", 0)
            if safe_to_spend > 0 or net_worth > 0:
                return VisualPayload.burndown_chart(
                    spent=0,  # Current period spent
                    budget=safe_to_spend,
                    ideal_pace=safe_to_spend * 0.5
                )

        # Handle budget overview
        elif tool_name == "get_budget_overview":
            # Check if it's from user plan or mock data
            if result_data.get("source") == "user_plan":
                categories = result_data.get("categories", [])
                safe_to_spend = result_data.get("safe_to_spend", 0)
                if categories:
                    return VisualPayload.spending_plan(safe_to_spend, categories)
            else:
                # Mock data - Return Sankey flow visualization
                nodes = result_data.get("nodes", [])
                if nodes:
                    return VisualPayload.sankey_flow([
                        SankeyNode(
                            id=node["id"],
                            name=node["name"],
                            value=node["value"]
                        )
                        for node in nodes
                    ])

        # Handle spending status
        elif tool_name == "get_spending_status":
            # Return burndown chart visualization
            return VisualPayload.burndown_chart(
                spent=result_data.get("spent", 0),
                budget=result_data.get("budget", 0),
                ideal_pace=result_data.get("idealPace", result_data.get("ideal_pace", 0))
            )

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

    if any(keyword in text_lower for keyword in ["budget", "overview", "spending breakdown"]):
        data = get_budget_overview_data()
        nodes = [SankeyNode(**node) for node in data["nodes"]]
        return AssistantResponse(
            text_message="Here's your budget overview. (Note: AI is temporarily unavailable)",
            visual_payload=VisualPayload.sankey_flow(nodes)
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
