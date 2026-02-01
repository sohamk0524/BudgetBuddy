"""
Orchestrator service - The "Brain" of BudgetBuddy.
Uses OpenAI SDK with Ollama for intelligent conversation and tool calling.
"""

from typing import Optional, Dict, Any
from models import AssistantResponse, VisualPayload, SankeyNode
from services.llm_service import BudgetBuddyAgent, OllamaConnectionError, OllamaError
from services.tools import get_tool_definitions, execute_tool
from services.data_mock import get_budget_overview_data, get_spending_status_data


# System prompt that guides conversation and tool usage
SYSTEM_PROMPT = """You are BudgetBuddy, a friendly AI financial assistant. You help users understand their finances, track spending, and make smart money decisions.

CONVERSATION GUIDELINES:
- Be warm, helpful, and conversational
- Keep responses concise (2-4 sentences for simple questions)
- For greetings like "hi", "hello", "hey" - just respond naturally and friendly, do NOT use any tools
- For general questions like "what can you do?" - explain your capabilities without using tools

WHEN TO USE TOOLS:
Only use tools when the user SPECIFICALLY asks about their financial data:
- get_budget_overview: ONLY when user says things like "show my budget", "spending breakdown", "where does my money go"
- get_spending_status: ONLY when user asks "can I afford...", "am I overspending", "budget status", "how am I doing financially"
- get_account_balance: ONLY when user asks "how much do I have", "my balance", "available money"
- get_savings_progress: ONLY when user asks about "savings", "saving goals", "progress toward goals"

DO NOT USE TOOLS FOR:
- Greetings (hi, hello, hey, good morning, etc.)
- General questions (how are you, what can you do, help me)
- Non-financial topics
- When the user is just chatting

RESPONSE STYLE:
- Be encouraging but honest about their financial situation
- When you do use a tool, explain the data in simple terms
- Use specific numbers from the tool results when available"""


# Initialize the agent
agent = BudgetBuddyAgent(model="llama3.2:3b")


def _should_use_tools(text: str) -> bool:
    """
    Determine if the message is likely asking about financial data.
    Only provide tools for finance-related queries to prevent over-eager tool calling.
    """
    text_lower = text.lower()

    # Keywords that suggest user wants financial data
    finance_keywords = [
        "budget", "spend", "spending", "expense", "expenses", "money",
        "afford", "cost", "balance", "account", "savings", "save",
        "income", "salary", "pay", "payment", "bill", "bills",
        "overview", "breakdown", "status", "track", "tracking",
        "how much", "how am i", "can i buy", "should i buy",
        "financial", "finances", "cash", "funds", "dollars", "$"
    ]

    return any(keyword in text_lower for keyword in finance_keywords)


def process_message(text: str, user_id: str = "default") -> AssistantResponse:
    """
    Process user message using the AI agent with optional tool calling.

    Args:
        text: The user's input message
        user_id: Optional user identifier for context

    Returns:
        AssistantResponse with text and optional visual payload
    """
    try:
        # Check if Ollama is available
        if not agent.is_available():
            return _fallback_response(
                text,
                "I'm having trouble connecting to my AI backend. Please make sure Ollama is running with 'ollama serve'."
            )

        # Build the conversation
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
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

        if tool_name == "get_budget_overview":
            # Return Sankey flow visualization
            nodes = result_data.get("nodes", [])
            return VisualPayload.sankey_flow([
                SankeyNode(
                    id=node["id"],
                    name=node["name"],
                    value=node["value"]
                )
                for node in nodes
            ])

        elif tool_name == "get_spending_status":
            # Return burndown chart visualization
            return VisualPayload.burndown_chart(
                spent=result_data.get("spent", 0),
                budget=result_data.get("budget", 0),
                ideal_pace=result_data.get("idealPace", 0)
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
