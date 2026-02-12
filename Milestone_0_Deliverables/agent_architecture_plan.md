# BudgetBuddy: Intelligent Agent Architecture Plan

## Executive Summary

This document outlines the transformation of BudgetBuddy's backend from a keyword-matching system into a **Sophisticated, Interwoven AI Agent** capable of complex reasoning, state awareness, and dynamic tool orchestration. The architecture is designed to be **general-purpose and extensible**, using the current features (plan creation, statement parsing) as illustrative examples while enabling seamless addition of future capabilities.

---

## Current State Analysis

### What Works Well
- **Tool-Using Agent Pattern**: Ollama + OpenAI SDK compatibility layer with 4 defined tools
- **Separation of Concerns**: Clear service boundaries (orchestrator, tools, llm_service, plan_generator)
- **Constraint-Based Tool Guarding**: Keyword filters + explicit prompt guidance
- **Strong iOS Client**: Type-safe Codable models, @Observable MVVM, extensible widget factory

### Key Limitations to Address
| Limitation | Impact |
|------------|--------|
| Stateless conversations | Agent has no memory between messages |
| Keyword-based routing | Brittle, doesn't scale to new features |
| Read-only tools | Cannot modify user state or take actions |
| No proactive behavior | Agent only reacts, never initiates |
| Fixed tool set | Adding tools requires code changes |
| No reasoning trace | Cannot explain decision-making |

---

## Part 1: The "Interwoven" State Machine

### 1.1 Concept: User Profile Health Monitor

The agent should continuously assess the "health" of the user's financial profile and proactively guide them toward a complete, optimized state. This transforms the agent from a passive Q&A bot into an **active financial companion**.

### 1.2 Architecture: Profile Health Assessment Engine

```
┌─────────────────────────────────────────────────────────────────┐
│                    PROFILE HEALTH ENGINE                         │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐         │
│  │   CRITICAL  │    │   WARNING   │    │    INFO     │         │
│  │  (Red Zone) │    │(Yellow Zone)│    │(Green Zone) │         │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘         │
│         │                  │                  │                 │
│  • No plan exists    • Plan is stale    • Budget on track      │
│  • No statement      • Overspending     • Goals progressing    │
│  • Profile empty     • Goal at risk     • Savings healthy      │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   STATE CONDITION REGISTRY                       │
├─────────────────────────────────────────────────────────────────┤
│  {                                                               │
│    "condition_id": "no_budget_plan",                            │
│    "severity": "critical",                                       │
│    "check": "SELECT ... WHERE has_plan = false",                │
│    "trigger_message": "I see you don't have a budget plan...",  │
│    "suggested_action": "initiate_plan_creation",                │
│    "cooldown_hours": 24                                          │
│  }                                                               │
└─────────────────────────────────────────────────────────────────┘
```

### 1.3 State Condition Schema

```python
@dataclass
class StateCondition:
    """Defines a detectable user state that may trigger agent intervention."""

    condition_id: str              # Unique identifier
    name: str                      # Human-readable name
    severity: Literal["critical", "warning", "info"]

    # Detection
    check_function: str            # Reference to checker function
    check_query: Optional[str]     # SQL query for data-driven checks

    # Response
    trigger_message: str           # What the agent says
    suggested_tool: Optional[str]  # Tool to offer/execute
    requires_confirmation: bool    # Ask before acting?

    # Rate limiting
    cooldown_hours: int            # Minimum hours between triggers
    max_triggers_per_week: int     # Prevent nagging

    # Context
    priority: int                  # Higher = check first
    supersedes: List[str]          # Conditions this overrides
```

### 1.4 Example State Conditions

#### Critical States (Immediate Attention)
```python
STATE_CONDITIONS = [
    StateCondition(
        condition_id="no_budget_plan",
        name="Missing Budget Plan",
        severity="critical",
        check_function="check_no_plan",
        trigger_message="I noticed you haven't created a budget plan yet. A personalized plan can help you track spending and reach your goals faster. Would you like to build one together?",
        suggested_tool="create_budget_plan",
        requires_confirmation=True,
        cooldown_hours=24,
        max_triggers_per_week=3,
        priority=100,
        supersedes=["stale_plan", "plan_needs_update"]
    ),

    StateCondition(
        condition_id="no_financial_profile",
        name="Incomplete Onboarding",
        severity="critical",
        check_function="check_no_profile",
        trigger_message="To give you personalized advice, I need to know a bit about your financial situation. Can we take 2 minutes to set up your profile?",
        suggested_tool="initiate_onboarding",
        requires_confirmation=True,
        cooldown_hours=48,
        max_triggers_per_week=2,
        priority=200,  # Higher than no_plan
        supersedes=["no_budget_plan"]
    ),
]
```

#### Warning States (Proactive Guidance)
```python
STATE_CONDITIONS += [
    StateCondition(
        condition_id="spending_velocity_high",
        name="Overspending Alert",
        severity="warning",
        check_function="check_spending_velocity",
        trigger_message="Heads up — you've spent {percent_of_budget}% of your monthly budget and we're only {days_elapsed} days in. Want me to show you where the money's going?",
        suggested_tool="get_spending_status",
        requires_confirmation=False,  # Just inform, tool offered
        cooldown_hours=72,
        max_triggers_per_week=2,
        priority=80,
        supersedes=[]
    ),

    StateCondition(
        condition_id="subscription_price_increase",
        name="Subscription Price Change Detected",
        severity="warning",
        check_function="check_subscription_changes",
        trigger_message="I noticed {subscription_name} increased from ${old_price} to ${new_price}. This adds ${annual_impact}/year to your expenses. Want to review your subscriptions?",
        suggested_tool="review_subscriptions",
        requires_confirmation=True,
        cooldown_hours=168,  # Once per week max
        max_triggers_per_week=1,
        priority=60,
        supersedes=[]
    ),

    StateCondition(
        condition_id="goal_at_risk",
        name="Savings Goal Behind Schedule",
        severity="warning",
        check_function="check_goal_progress",
        trigger_message="Your '{goal_name}' goal is {percent_behind}% behind schedule. At current pace, you'll reach it {months_late} months late. Should we adjust your budget to catch up?",
        suggested_tool="adjust_savings_allocation",
        requires_confirmation=True,
        cooldown_hours=168,
        max_triggers_per_week=1,
        priority=70,
        supersedes=[]
    ),
]
```

#### Info States (Positive Reinforcement)
```python
STATE_CONDITIONS += [
    StateCondition(
        condition_id="under_budget_milestone",
        name="Under Budget Achievement",
        severity="info",
        check_function="check_under_budget",
        trigger_message="Great news! You're {percent_under}% under budget this month. You could put that extra ${amount} toward your {top_goal} goal!",
        suggested_tool=None,
        requires_confirmation=False,
        cooldown_hours=168,
        max_triggers_per_week=1,
        priority=20,
        supersedes=[]
    ),

    StateCondition(
        condition_id="goal_milestone_reached",
        name="Savings Milestone",
        severity="info",
        check_function="check_goal_milestones",
        trigger_message="Congratulations! You've hit {milestone}% of your '{goal_name}' goal! Keep it up — only ${remaining} to go.",
        suggested_tool=None,
        requires_confirmation=False,
        cooldown_hours=168,
        max_triggers_per_week=2,
        priority=10,
        supersedes=[]
    ),
]
```

### 1.5 State Engine Implementation

```python
# services/state_engine.py

class ProfileHealthEngine:
    """Monitors user state and triggers proactive agent behaviors."""

    def __init__(self, db_session, condition_registry: List[StateCondition]):
        self.db = db_session
        self.conditions = sorted(condition_registry, key=lambda c: -c.priority)
        self.checkers = self._load_checkers()

    def assess_user_health(self, user_id: int) -> List[TriggeredCondition]:
        """
        Evaluate all conditions for a user.
        Returns list of triggered conditions, respecting cooldowns and supersession.
        """
        triggered = []
        superseded_ids = set()

        for condition in self.conditions:
            if condition.condition_id in superseded_ids:
                continue

            if self._is_on_cooldown(user_id, condition):
                continue

            result = self._check_condition(user_id, condition)
            if result.triggered:
                triggered.append(TriggeredCondition(
                    condition=condition,
                    context=result.context  # Dynamic values for message template
                ))
                superseded_ids.update(condition.supersedes)

        return triggered

    def get_greeting_context(self, user_id: int) -> AgentContext:
        """
        Called on session start. Returns context for agent's opening message.
        """
        triggered = self.assess_user_health(user_id)

        if not triggered:
            return AgentContext(
                greeting_override=None,
                suggested_actions=[],
                health_summary=self._build_health_summary(user_id)
            )

        # Return highest priority triggered condition
        top_condition = triggered[0]
        return AgentContext(
            greeting_override=self._format_message(top_condition),
            suggested_actions=[t.condition.suggested_tool for t in triggered if t.condition.suggested_tool],
            health_summary=self._build_health_summary(user_id),
            triggered_conditions=triggered
        )

    def _check_condition(self, user_id: int, condition: StateCondition) -> CheckResult:
        """Execute the check function for a condition."""
        checker = self.checkers.get(condition.check_function)
        if not checker:
            return CheckResult(triggered=False)

        return checker(self.db, user_id)
```

### 1.6 Integration with Chat Flow

```python
# services/orchestrator.py (updated)

class AgentOrchestrator:
    def __init__(self, db_session, llm_agent, tool_registry, state_engine):
        self.db = db_session
        self.llm = llm_agent
        self.tools = tool_registry
        self.state_engine = state_engine
        self.conversation_manager = ConversationManager()

    async def process_message(
        self,
        user_id: int,
        message: str,
        session_id: str,
        is_session_start: bool = False
    ) -> AssistantResponse:
        """
        Main entry point for all user interactions.
        """
        # 1. Load conversation context
        context = self.conversation_manager.get_context(session_id)

        # 2. Check for proactive interventions (especially on session start)
        if is_session_start or self._should_check_health(context):
            health_context = self.state_engine.get_greeting_context(user_id)

            if health_context.greeting_override:
                # Agent has something important to say
                response = await self._handle_proactive_intervention(
                    user_id, health_context, context
                )
                if response:
                    return response

        # 3. Process user message through reasoning engine
        return await self._process_with_reasoning(user_id, message, context)
```

### 1.7 Extensibility Pattern

Adding a new state condition requires only:

```python
# 1. Define the condition
new_condition = StateCondition(
    condition_id="recurring_charge_anomaly",
    name="Unusual Recurring Charge",
    severity="warning",
    check_function="check_recurring_anomalies",
    trigger_message="I noticed an unusual charge of ${amount} from {merchant}...",
    ...
)

# 2. Implement the checker
@register_checker("check_recurring_anomalies")
def check_recurring_anomalies(db, user_id) -> CheckResult:
    # Query transaction history
    # Detect anomalies
    # Return result with context
    pass

# 3. Add to registry (or auto-discovered via decorator)
STATE_CONDITIONS.append(new_condition)
```

---

## Part 2: The Scalable Tool Registry

### 2.1 Concept: Declarative Tool System

Tools should be **self-describing**, **composable**, and **hot-pluggable**. The LLM selects tools based on their descriptions, and the backend executes them with proper validation, logging, and error handling.

### 2.2 Architecture: Universal Tool Interface

```
┌─────────────────────────────────────────────────────────────────┐
│                      TOOL REGISTRY                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    TOOL DEFINITION                        │   │
│  ├──────────────────────────────────────────────────────────┤   │
│  │  name: "parse_bank_statement"                            │   │
│  │  category: "document_processing"                          │   │
│  │  description: "Extract transactions from uploaded..."     │   │
│  │  parameters: JSONSchema { file_id, analysis_depth }       │   │
│  │  returns: JSONSchema { transactions, summary, insights }  │   │
│  │  requires: ["file_upload"]                                │   │
│  │  produces: ["financial_data", "visual:sankeyFlow"]        │   │
│  │  side_effects: ["updates_financial_profile"]              │   │
│  │  confirmation_required: false                             │   │
│  │  example_triggers: ["analyze my statement", ...]          │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              │                                   │
│                              ▼                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                   TOOL EXECUTOR                           │   │
│  ├──────────────────────────────────────────────────────────┤   │
│  │  async def execute(context: ToolContext) -> ToolResult    │   │
│  │                                                           │   │
│  │  - Validates input against parameter schema               │   │
│  │  - Executes business logic                                │   │
│  │  - Produces structured output                             │   │
│  │  - Emits events for side effects                          │   │
│  │  - Returns result + visual payload                        │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 2.3 Tool Definition Schema

```python
# tools/base.py

@dataclass
class ToolParameter:
    name: str
    type: Literal["string", "number", "boolean", "array", "object", "file"]
    description: str
    required: bool = True
    default: Any = None
    enum: Optional[List[Any]] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None

@dataclass
class ToolDefinition:
    """Complete specification of a tool's interface and behavior."""

    # Identity
    name: str                          # Unique tool identifier
    display_name: str                  # Human-friendly name
    category: str                      # Grouping: "analysis", "planning", "tracking"

    # LLM Interface
    description: str                   # What the tool does (for LLM)
    when_to_use: str                   # Explicit guidance (ONLY use when...)
    when_not_to_use: str               # Anti-patterns
    example_triggers: List[str]        # Sample user intents

    # Parameters
    parameters: List[ToolParameter]    # Input specification
    returns: Dict[str, Any]            # Output JSON schema

    # Capabilities
    requires: List[str]                # Prerequisites: ["authenticated", "has_statement"]
    produces: List[str]                # Outputs: ["visual:sankeyFlow", "data:transactions"]

    # Safety
    side_effects: List[str]            # What it modifies: ["updates_profile", "sends_email"]
    confirmation_required: bool        # Ask user before executing?
    is_destructive: bool               # Can it delete data?

    # Execution
    timeout_seconds: int = 30
    retry_policy: RetryPolicy = RetryPolicy.default()

    def to_openai_schema(self) -> Dict[str, Any]:
        """Convert to OpenAI function calling format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": f"{self.description}\n\n{self.when_to_use}",
                "parameters": self._build_parameter_schema()
            }
        }
```

### 2.4 Tool Implementation Pattern

```python
# tools/statement_parser.py

from tools.base import Tool, ToolDefinition, ToolContext, ToolResult

class ParseBankStatementTool(Tool):
    """Tool for parsing and analyzing bank statements."""

    definition = ToolDefinition(
        name="parse_bank_statement",
        display_name="Bank Statement Analyzer",
        category="document_processing",

        description="Parses an uploaded bank statement (PDF or CSV) and extracts transaction data, balances, and spending patterns.",

        when_to_use="ONLY use when the user has explicitly uploaded a bank statement file and wants it analyzed. Do not use for general questions about their finances.",

        when_not_to_use="Do not use when asking about spending without a recent upload, or for hypothetical scenarios.",

        example_triggers=[
            "analyze my bank statement",
            "what does my statement show",
            "parse this PDF",
            "show me my transactions"
        ],

        parameters=[
            ToolParameter(
                name="file_id",
                type="string",
                description="The ID of the uploaded file to analyze",
                required=True
            ),
            ToolParameter(
                name="analysis_depth",
                type="string",
                description="Level of analysis: 'quick' for summary, 'detailed' for full breakdown",
                required=False,
                default="detailed",
                enum=["quick", "detailed"]
            )
        ],

        returns={
            "type": "object",
            "properties": {
                "transactions": {"type": "array"},
                "summary": {"type": "object"},
                "insights": {"type": "array"},
                "visual": {"type": "object"}
            }
        },

        requires=["authenticated", "file_uploaded"],
        produces=["data:transactions", "data:spending_summary", "visual:categoryBreakdown"],
        side_effects=["updates_saved_statement"],
        confirmation_required=False,
        is_destructive=False
    )

    async def execute(self, context: ToolContext) -> ToolResult:
        """Execute the statement parsing logic."""

        # 1. Validate prerequisites
        if not context.has_uploaded_file(context.params["file_id"]):
            return ToolResult.error("No file found with that ID")

        # 2. Get the file
        file_data = await context.get_file(context.params["file_id"])

        # 3. Parse based on file type
        if file_data.type == "pdf":
            parsed = await self._parse_pdf(file_data.content)
        elif file_data.type == "csv":
            parsed = await self._parse_csv(file_data.content)
        else:
            return ToolResult.error(f"Unsupported file type: {file_data.type}")

        # 4. Run LLM categorization
        categorized = await self._categorize_transactions(parsed.transactions, context.llm)

        # 5. Build insights
        insights = self._generate_insights(categorized)

        # 6. Persist to database
        await context.db.save_statement(
            user_id=context.user_id,
            parsed_data=categorized,
            insights=insights
        )

        # 7. Build visual payload
        visual = VisualPayload.category_breakdown(
            categories=categorized.by_category,
            total=categorized.total_spending
        )

        # 8. Return structured result
        return ToolResult.success(
            data={
                "transactions": categorized.transactions,
                "summary": categorized.summary,
                "insights": insights
            },
            visual=visual,
            message=self._format_summary(categorized, insights)
        )
```

### 2.5 Tool Registry Implementation

```python
# tools/registry.py

class ToolRegistry:
    """Central registry for all available tools."""

    def __init__(self):
        self._tools: Dict[str, Tool] = {}
        self._categories: Dict[str, List[str]] = defaultdict(list)
        self._hooks: List[ToolHook] = []

    def register(self, tool: Tool) -> None:
        """Register a tool in the registry."""
        if tool.definition.name in self._tools:
            raise ValueError(f"Tool {tool.definition.name} already registered")

        self._tools[tool.definition.name] = tool
        self._categories[tool.definition.category].append(tool.definition.name)
        logger.info(f"Registered tool: {tool.definition.name}")

    def register_hook(self, hook: ToolHook) -> None:
        """Register a hook for tool execution events."""
        self._hooks.append(hook)

    def get(self, name: str) -> Optional[Tool]:
        """Get a tool by name."""
        return self._tools.get(name)

    def get_available_tools(self, context: ToolContext) -> List[Tool]:
        """Get tools available given current context (respecting prerequisites)."""
        available = []
        for tool in self._tools.values():
            if self._check_prerequisites(tool, context):
                available.append(tool)
        return available

    def get_openai_schemas(self, context: ToolContext) -> List[Dict]:
        """Get OpenAI function schemas for available tools."""
        return [
            tool.definition.to_openai_schema()
            for tool in self.get_available_tools(context)
        ]

    async def execute(self, name: str, params: Dict, context: ToolContext) -> ToolResult:
        """Execute a tool with full lifecycle management."""
        tool = self.get(name)
        if not tool:
            return ToolResult.error(f"Unknown tool: {name}")

        # Pre-execution hooks
        for hook in self._hooks:
            await hook.before_execute(tool, params, context)

        # Validate parameters
        validation = tool.validate_params(params)
        if not validation.valid:
            return ToolResult.error(f"Invalid parameters: {validation.errors}")

        # Check confirmation requirement
        if tool.definition.confirmation_required and not context.user_confirmed:
            return ToolResult.needs_confirmation(
                message=f"This action will {tool.definition.side_effects}. Proceed?",
                tool_name=name,
                params=params
            )

        # Execute with timeout
        try:
            result = await asyncio.wait_for(
                tool.execute(context.with_params(params)),
                timeout=tool.definition.timeout_seconds
            )
        except asyncio.TimeoutError:
            result = ToolResult.error(f"Tool execution timed out after {tool.definition.timeout_seconds}s")
        except Exception as e:
            logger.exception(f"Tool {name} failed")
            result = ToolResult.error(f"Tool execution failed: {str(e)}")

        # Post-execution hooks
        for hook in self._hooks:
            await hook.after_execute(tool, params, context, result)

        return result

    def _check_prerequisites(self, tool: Tool, context: ToolContext) -> bool:
        """Check if all prerequisites for a tool are met."""
        for req in tool.definition.requires:
            if req == "authenticated" and not context.is_authenticated:
                return False
            if req == "has_statement" and not context.has_statement:
                return False
            if req == "has_plan" and not context.has_plan:
                return False
            if req == "file_uploaded" and not context.pending_files:
                return False
        return True


# Auto-discovery and registration
def create_tool_registry() -> ToolRegistry:
    """Create and populate the tool registry."""
    registry = ToolRegistry()

    # Auto-discover tools from the tools package
    for tool_class in discover_tools("tools"):
        registry.register(tool_class())

    # Register logging hook
    registry.register_hook(LoggingHook())

    # Register analytics hook
    registry.register_hook(AnalyticsHook())

    return registry
```

### 2.6 Illustrative Tool Implementations

#### Tool: CreateBudgetPlan
```python
class CreateBudgetPlanTool(Tool):
    definition = ToolDefinition(
        name="create_budget_plan",
        display_name="Budget Plan Creator",
        category="planning",

        description="Creates a personalized monthly budget plan based on the user's income, expenses, and financial goals.",

        when_to_use="Use when the user explicitly wants to create or update their budget plan, OR when the state engine detects they have no plan.",

        when_not_to_use="Do not use for simple questions about budgeting concepts or when the user is just asking about their current spending.",

        parameters=[
            ToolParameter(
                name="deep_dive_data",
                type="object",
                description="Detailed financial information collected via the plan questionnaire",
                required=False  # Will fetch from profile if not provided
            ),
            ToolParameter(
                name="optimization_goal",
                type="string",
                description="What to optimize for",
                required=False,
                default="balanced",
                enum=["maximize_savings", "minimize_debt", "balanced", "quality_of_life"]
            )
        ],

        requires=["authenticated", "has_profile"],
        produces=["data:budget_plan", "visual:spendingPlan"],
        side_effects=["creates_budget_plan"],
        confirmation_required=True,
        is_destructive=False
    )

    async def execute(self, context: ToolContext) -> ToolResult:
        # Implementation uses existing plan_generator.py logic
        ...
```

#### Tool: TrackTransaction
```python
class TrackTransactionTool(Tool):
    """Example of a write operation tool."""

    definition = ToolDefinition(
        name="track_transaction",
        display_name="Transaction Tracker",
        category="tracking",

        description="Manually logs a transaction (expense or income) to the user's financial record.",

        when_to_use="Use when the user wants to record a purchase, expense, or income they just made.",

        parameters=[
            ToolParameter(name="amount", type="number", description="Transaction amount", required=True),
            ToolParameter(name="category", type="string", description="Spending category", required=True),
            ToolParameter(name="merchant", type="string", description="Where the transaction occurred", required=False),
            ToolParameter(name="date", type="string", description="Transaction date (ISO format)", required=False),
            ToolParameter(name="notes", type="string", description="Optional notes", required=False)
        ],

        requires=["authenticated"],
        produces=["data:transaction_logged"],
        side_effects=["creates_transaction", "updates_spending_totals"],
        confirmation_required=False,
        is_destructive=False
    )
```

### 2.7 Making the Agent Feel Like the App

To create an immersive experience where the agent **is** the app (not a separate feature), we implement:

```python
# tools/ui_integration.py

class UIIntegrationMixin:
    """Mixin that allows tools to trigger UI navigation and state changes."""

    async def suggest_navigation(self, context: ToolContext, destination: str) -> None:
        """Suggest the UI should navigate to a specific screen."""
        context.emit_event(UIEvent(
            type="navigation_suggestion",
            destination=destination,  # "wallet", "plan", "chat", "settings"
            reason=self.definition.display_name
        ))

    async def update_widget(self, context: ToolContext, widget_id: str, data: Dict) -> None:
        """Push real-time updates to a UI widget."""
        context.emit_event(UIEvent(
            type="widget_update",
            widget_id=widget_id,
            data=data
        ))

    async def show_inline_action(self, context: ToolContext, action: InlineAction) -> None:
        """Show an actionable button/card in the chat."""
        context.emit_event(UIEvent(
            type="inline_action",
            action=action  # e.g., "tap to add transaction", "view full breakdown"
        ))
```

```python
# Response includes UI directives
class ToolResult:
    data: Dict[str, Any]
    message: str
    visual: Optional[VisualPayload]
    ui_events: List[UIEvent]  # Navigation hints, widget updates, etc.
    follow_up_suggestions: List[str]  # "Would you like to..." options
```

---

## Part 3: Multi-Modal & Contextual Input

### 3.1 Concept: Eyes and Memory

The agent needs:
1. **Eyes**: Ability to "see" and understand uploaded documents (PDFs, CSVs, images)
2. **Memory**: Persistent context within a session and awareness of long-term user history

### 3.2 Architecture: Unified Input Processing Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│                    INPUT PROCESSING PIPELINE                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   USER INPUT                                                     │
│       │                                                          │
│       ▼                                                          │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │              INPUT CLASSIFIER                            │   │
│   │  • Text message                                          │   │
│   │  • File upload (PDF, CSV, image)                         │   │
│   │  • Voice transcript                                      │   │
│   │  • Quick action (button tap)                             │   │
│   └─────────────────────────────────────────────────────────┘   │
│       │                                                          │
│       ├── Text ──────────► NLU Pipeline                         │
│       │                                                          │
│       ├── PDF ───────────► Document Processor ──► Text Extract  │
│       │                         │                                │
│       │                         ▼                                │
│       │                    Table Parser ──► Structured Data      │
│       │                                                          │
│       ├── CSV ───────────► CSV Parser ──► Structured Data        │
│       │                                                          │
│       └── Image ─────────► OCR Pipeline ──► Text Extract         │
│                                                                  │
│       ALL PATHS                                                  │
│           │                                                      │
│           ▼                                                      │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │              CONTEXT ENRICHMENT                          │   │
│   │  • Merge with conversation history                       │   │
│   │  • Add user profile context                              │   │
│   │  • Attach relevant financial data                        │   │
│   │  • Resolve references ("that subscription")              │   │
│   └─────────────────────────────────────────────────────────┘   │
│           │                                                      │
│           ▼                                                      │
│       ENRICHED CONTEXT ──► Agent Reasoning Engine                │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 3.3 File Upload Handling

```python
# services/document_processor.py

class DocumentProcessor:
    """Handles multi-modal document input."""

    def __init__(self, ocr_service: OCRService, llm_service: LLMService):
        self.ocr = ocr_service
        self.llm = llm_service
        self.parsers = {
            "pdf": PDFParser(),
            "csv": CSVParser(),
            "png": ImageParser(),
            "jpg": ImageParser(),
        }

    async def process(self, file: UploadedFile, context: ProcessingContext) -> DocumentResult:
        """
        Process an uploaded file and extract structured financial data.
        """
        parser = self.parsers.get(file.extension)
        if not parser:
            raise UnsupportedFileTypeError(file.extension)

        # 1. Extract raw content
        raw_content = await parser.extract(file.content)

        # 2. Detect document type (bank statement, receipt, invoice, etc.)
        doc_type = await self._classify_document(raw_content)

        # 3. Extract structured data based on type
        if doc_type == "bank_statement":
            structured = await self._extract_statement_data(raw_content)
        elif doc_type == "receipt":
            structured = await self._extract_receipt_data(raw_content)
        else:
            structured = {"raw_text": raw_content.text}

        # 4. Merge into user's FinancialProfile
        if structured.get("transactions"):
            await self._merge_transactions(context.user_id, structured["transactions"])

        return DocumentResult(
            document_type=doc_type,
            structured_data=structured,
            raw_text=raw_content.text,
            confidence=raw_content.confidence,
            file_id=file.id
        )

    async def _classify_document(self, content: RawContent) -> str:
        """Use LLM to classify document type."""
        prompt = f"""Classify this document into one of: bank_statement, receipt, invoice, pay_stub, tax_document, other.

Document preview:
{content.text[:2000]}

Respond with just the document type."""

        response = await self.llm.chat(prompt)
        return response.strip().lower()
```

### 3.4 Conversation Memory System

```python
# services/conversation_manager.py

@dataclass
class ConversationTurn:
    role: Literal["user", "assistant", "system", "tool"]
    content: str
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    # For tool calls
    tool_name: Optional[str] = None
    tool_args: Optional[Dict] = None
    tool_result: Optional[Dict] = None

@dataclass
class ConversationContext:
    session_id: str
    user_id: int
    turns: List[ConversationTurn]

    # Extracted entities for reference resolution
    mentioned_subscriptions: List[str]
    mentioned_categories: List[str]
    mentioned_goals: List[str]
    mentioned_amounts: List[float]

    # Current focus
    active_topic: Optional[str]
    pending_confirmation: Optional[PendingAction]

    def get_recent_context(self, max_turns: int = 10) -> List[Dict]:
        """Get recent turns formatted for LLM context."""
        return [
            {"role": turn.role, "content": turn.content}
            for turn in self.turns[-max_turns:]
        ]

    def resolve_reference(self, reference: str) -> Optional[Any]:
        """
        Resolve anaphoric references like "that subscription" or "it".
        """
        ref_lower = reference.lower()

        if "subscription" in ref_lower and self.mentioned_subscriptions:
            return {"type": "subscription", "value": self.mentioned_subscriptions[-1]}

        if "goal" in ref_lower and self.mentioned_goals:
            return {"type": "goal", "value": self.mentioned_goals[-1]}

        if "category" in ref_lower and self.mentioned_categories:
            return {"type": "category", "value": self.mentioned_categories[-1]}

        return None


class ConversationManager:
    """Manages conversation state and memory."""

    def __init__(self, db_session, cache: CacheService):
        self.db = db_session
        self.cache = cache
        self.entity_extractor = EntityExtractor()

    async def get_context(self, session_id: str) -> ConversationContext:
        """Load or create conversation context."""
        # Try cache first
        cached = await self.cache.get(f"conversation:{session_id}")
        if cached:
            return ConversationContext(**cached)

        # Create new context
        return ConversationContext(
            session_id=session_id,
            user_id=0,  # Will be set on first message
            turns=[],
            mentioned_subscriptions=[],
            mentioned_categories=[],
            mentioned_goals=[],
            mentioned_amounts=[],
            active_topic=None,
            pending_confirmation=None
        )

    async def add_turn(
        self,
        session_id: str,
        turn: ConversationTurn,
        extract_entities: bool = True
    ) -> None:
        """Add a turn to the conversation and update context."""
        context = await self.get_context(session_id)
        context.turns.append(turn)

        # Extract entities from user messages
        if extract_entities and turn.role == "user":
            entities = await self.entity_extractor.extract(turn.content)
            context.mentioned_subscriptions.extend(entities.subscriptions)
            context.mentioned_categories.extend(entities.categories)
            context.mentioned_goals.extend(entities.goals)
            context.mentioned_amounts.extend(entities.amounts)

        # Persist
        await self.cache.set(
            f"conversation:{session_id}",
            asdict(context),
            ttl=3600  # 1 hour session
        )

    async def build_llm_context(
        self,
        session_id: str,
        user_id: int
    ) -> List[Dict]:
        """
        Build complete context for LLM including:
        - System prompt with user profile
        - Recent conversation history
        - Current financial state summary
        """
        context = await self.get_context(session_id)
        user_profile = await self.db.get_financial_profile(user_id)
        current_state = await self.db.get_financial_summary(user_id)

        messages = []

        # System message with user context
        messages.append({
            "role": "system",
            "content": self._build_system_prompt(user_profile, current_state)
        })

        # Conversation history
        messages.extend(context.get_recent_context())

        return messages

    def _build_system_prompt(self, profile: FinancialProfile, state: FinancialSummary) -> str:
        return f"""You are BudgetBuddy, a helpful financial assistant.

## User Context
- Name: {profile.name or 'User'}
- Monthly Income: ${profile.income:,.2f}
- Financial Personality: {profile.financial_personality}
- Primary Goal: {profile.primary_goal}

## Current Financial State
- Safe to Spend: ${state.safe_to_spend:,.2f}
- Spent This Month: ${state.spent_this_month:,.2f}
- Budget Remaining: ${state.budget_remaining:,.2f}
- Days Left in Month: {state.days_remaining}

## Guidelines
- Be concise and friendly
- Reference their specific numbers when relevant
- Suggest tools when appropriate for their needs
- Remember context from earlier in this conversation
"""
```

### 3.5 Reference Resolution

```python
# services/reference_resolver.py

class ReferenceResolver:
    """Resolves pronouns and references in user messages."""

    async def resolve(self, message: str, context: ConversationContext) -> str:
        """
        Expand references in a message to their full form.

        "Cancel that subscription" -> "Cancel Netflix subscription"
        "How much did I spend on it?" -> "How much did I spend on groceries?"
        """
        patterns = [
            (r'\bthat subscription\b', self._resolve_subscription),
            (r'\bthe subscription\b', self._resolve_subscription),
            (r'\bthat goal\b', self._resolve_goal),
            (r'\bthis category\b', self._resolve_category),
            (r'\bit\b(?=\s|$|[.,!?])', self._resolve_it),
        ]

        resolved = message
        for pattern, resolver in patterns:
            match = re.search(pattern, resolved, re.IGNORECASE)
            if match:
                replacement = await resolver(context)
                if replacement:
                    resolved = re.sub(pattern, replacement, resolved, count=1, flags=re.IGNORECASE)

        return resolved

    async def _resolve_subscription(self, context: ConversationContext) -> Optional[str]:
        if context.mentioned_subscriptions:
            return context.mentioned_subscriptions[-1]
        return None

    async def _resolve_it(self, context: ConversationContext) -> Optional[str]:
        """Resolve 'it' based on conversation topic."""
        if context.active_topic == "subscription" and context.mentioned_subscriptions:
            return context.mentioned_subscriptions[-1]
        if context.active_topic == "category" and context.mentioned_categories:
            return f"the {context.mentioned_categories[-1]} category"
        return None
```

---

## Part 4: Implementation Roadmap

### Phase Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    IMPLEMENTATION PHASES                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  PHASE 1: THE BRAIN (Weeks 1-2)                                 │
│  ├── LLM Router with Reasoning                                  │
│  ├── Tool Registry Infrastructure                               │
│  ├── Conversation Memory                                        │
│  └── Basic Context Building                                     │
│                                                                  │
│  PHASE 2: THE CORE TOOLS (Weeks 3-4)                            │
│  ├── Migrate Existing Tools to New System                       │
│  ├── Implement Write Operations                                 │
│  ├── Enhanced Document Processing                               │
│  └── Visual Payload System                                      │
│                                                                  │
│  PHASE 3: THE EXPANSION (Weeks 5-6)                             │
│  ├── Profile Health Engine                                      │
│  ├── Proactive Interventions                                    │
│  ├── Advanced Reference Resolution                              │
│  └── Analytics & Optimization                                   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

### Phase 1: The Brain

**Goal**: Replace keyword-based routing with intelligent LLM orchestration.

#### 1.1 LLM Router with ReAct Pattern

```python
# services/reasoning_engine.py

class ReasoningEngine:
    """
    Implements ReAct (Reasoning + Acting) pattern for agent decision-making.
    """

    async def process(self, user_input: str, context: AgentContext) -> AgentResponse:
        """
        Main reasoning loop:
        1. Thought: What does the user want?
        2. Action: What tool (if any) should I use?
        3. Observation: What did the tool return?
        4. Repeat until ready to respond
        """
        messages = context.conversation_history + [
            {"role": "user", "content": user_input}
        ]

        max_iterations = 5
        for i in range(max_iterations):
            # Get LLM response with tool options
            response = await self.llm.chat_with_tools(
                messages=messages,
                tools=context.available_tools,
                tool_choice="auto"
            )

            # Check if LLM wants to use a tool
            if response.tool_calls:
                for tool_call in response.tool_calls:
                    # Execute tool
                    result = await self.tool_registry.execute(
                        tool_call.name,
                        tool_call.arguments,
                        context
                    )

                    # Add observation to messages
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(result.data)
                    })
            else:
                # LLM is ready to respond to user
                return AgentResponse(
                    text=response.content,
                    visual=self._extract_visual(response, context),
                    reasoning_trace=messages  # For debugging
                )

        # Max iterations reached
        return AgentResponse(
            text="I wasn't able to complete that request. Could you try rephrasing?",
            visual=None
        )
```

#### 1.2 Tool Registry Infrastructure

**Files to create**:
- `tools/base.py` - Base classes and schemas
- `tools/registry.py` - Tool registry implementation
- `tools/__init__.py` - Auto-discovery

**Migration strategy**:
1. Create new tool base classes
2. Wrap existing `tools.py` functions in new `Tool` classes
3. Update orchestrator to use new registry
4. Deprecate old `TOOL_DEFINITIONS` / `TOOL_EXECUTORS`

#### 1.3 Conversation Memory

**Files to create**:
- `services/conversation_manager.py` - Session management
- `services/cache.py` - Redis/in-memory cache abstraction

**Database changes**:
```sql
CREATE TABLE conversation_sessions (
    id TEXT PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    started_at TIMESTAMP,
    last_activity TIMESTAMP,
    context_json TEXT
);

CREATE TABLE conversation_turns (
    id INTEGER PRIMARY KEY,
    session_id TEXT REFERENCES conversation_sessions(id),
    role TEXT,
    content TEXT,
    tool_name TEXT,
    tool_args TEXT,
    tool_result TEXT,
    created_at TIMESTAMP
);
```

#### 1.4 Deliverables

| Deliverable | Description |
|-------------|-------------|
| `ReasoningEngine` class | ReAct-style reasoning loop |
| `ToolRegistry` class | Centralized tool management |
| `ConversationManager` class | Session and memory handling |
| Updated `/chat` endpoint | Uses new orchestration |
| Unit tests | Coverage for new components |

---

### Phase 2: The Core Tools

**Goal**: Implement robust versions of essential tools and add write capabilities.

#### 2.1 Migrate Existing Tools

Convert current tools to new format:

| Current | New Class | Enhancements |
|---------|-----------|--------------|
| `get_budget_overview` | `BudgetOverviewTool` | Add date range params, comparison mode |
| `get_spending_status` | `SpendingStatusTool` | Add category filter, trend analysis |
| `get_account_balance` | `AccountBalanceTool` | Multi-account support |
| `get_savings_progress` | `SavingsProgressTool` | Projection calculations |

#### 2.2 New Write Operation Tools

```python
# New tools to implement

class TrackTransactionTool(Tool):
    """Manually log a transaction."""
    name = "track_transaction"
    side_effects = ["creates_transaction"]

class UpdateBudgetCategoryTool(Tool):
    """Adjust budget allocation for a category."""
    name = "update_budget_category"
    side_effects = ["updates_budget_plan"]
    confirmation_required = True

class SetSavingsGoalTool(Tool):
    """Create or update a savings goal."""
    name = "set_savings_goal"
    side_effects = ["updates_goals"]

class CancelSubscriptionReminderTool(Tool):
    """Set a reminder to cancel a subscription."""
    name = "set_cancellation_reminder"
    side_effects = ["creates_reminder"]
```

#### 2.3 Enhanced Document Processing

Upgrade `statement_analyzer.py`:

```python
class EnhancedStatementAnalyzer:
    """
    Improvements over current implementation:
    1. Better PDF parsing (handle more bank formats)
    2. Smarter transaction categorization
    3. Anomaly detection (unusual charges)
    4. Recurring transaction identification
    5. Balance reconciliation
    """

    async def analyze(self, file: UploadedFile, context: ToolContext) -> StatementAnalysis:
        # 1. Parse document
        parsed = await self.parser.parse(file)

        # 2. Identify recurring transactions
        recurring = self._identify_recurring(parsed.transactions)

        # 3. Detect anomalies
        anomalies = self._detect_anomalies(parsed.transactions, context.user_history)

        # 4. Categorize with LLM assistance
        categorized = await self._categorize_transactions(parsed.transactions)

        # 5. Generate insights
        insights = self._generate_insights(categorized, recurring, anomalies)

        return StatementAnalysis(
            transactions=categorized,
            recurring=recurring,
            anomalies=anomalies,
            insights=insights,
            visual=self._build_visual(categorized)
        )
```

#### 2.4 Visual Payload System

Extend `models.py`:

```python
class VisualPayload:
    """Extended visual payload types."""

    @staticmethod
    def comparison_chart(current: dict, previous: dict) -> dict:
        """Month-over-month comparison."""
        return {"type": "comparisonChart", "current": current, "previous": previous}

    @staticmethod
    def goal_progress(goals: List[dict]) -> dict:
        """Multiple goals progress view."""
        return {"type": "goalProgress", "goals": goals}

    @staticmethod
    def transaction_list(transactions: List[dict], filters: dict) -> dict:
        """Scrollable transaction list with filters."""
        return {"type": "transactionList", "transactions": transactions, "filters": filters}

    @staticmethod
    def action_card(title: str, actions: List[dict]) -> dict:
        """Card with actionable buttons."""
        return {"type": "actionCard", "title": title, "actions": actions}
```

#### 2.5 Deliverables

| Deliverable | Description |
|-------------|-------------|
| 4 migrated tools | Existing tools in new format |
| 4 new write tools | Transaction tracking, budget updates, goals, reminders |
| Enhanced statement analyzer | Better parsing, categorization, insights |
| Extended visual payloads | 4 new visualization types |
| Integration tests | End-to-end tool testing |

---

### Phase 3: The Expansion

**Goal**: Implement proactive behaviors and optimize the user experience.

#### 3.1 Profile Health Engine

Implement the state machine described in Part 1:

```python
# services/state_engine.py

class ProfileHealthEngine:
    """Monitors user state and triggers proactive behaviors."""

    def __init__(self):
        self.conditions = self._load_conditions()
        self.checkers = self._load_checkers()

    def assess(self, user_id: int) -> HealthAssessment:
        """Run all condition checks and return assessment."""
        ...
```

**Initial condition set**:
1. `no_budget_plan` - Critical
2. `no_financial_profile` - Critical
3. `spending_velocity_high` - Warning
4. `goal_at_risk` - Warning
5. `subscription_price_increase` - Warning
6. `under_budget_milestone` - Info
7. `goal_milestone_reached` - Info

#### 3.2 Proactive Intervention System

```python
# services/proactive_manager.py

class ProactiveManager:
    """Manages proactive agent interventions."""

    async def check_and_intervene(
        self,
        user_id: int,
        trigger: str  # "session_start", "post_transaction", "daily_check"
    ) -> Optional[ProactiveMessage]:
        """
        Check if the agent should proactively message the user.
        """
        # Get triggered conditions
        health = self.health_engine.assess(user_id)

        if not health.triggered_conditions:
            return None

        # Respect rate limits
        filtered = self._apply_rate_limits(user_id, health.triggered_conditions)

        if not filtered:
            return None

        # Get highest priority
        top = filtered[0]

        # Build message
        message = self._format_intervention(top)

        # Log intervention
        await self._log_intervention(user_id, top)

        return message
```

#### 3.3 Advanced Reference Resolution

```python
# services/entity_tracker.py

class EntityTracker:
    """
    Tracks entities mentioned in conversation for reference resolution.
    Uses both rule-based and LLM-assisted resolution.
    """

    async def resolve_references(
        self,
        message: str,
        context: ConversationContext
    ) -> ResolvedMessage:
        """
        Resolve all references in a message.

        Input: "Cancel that and reduce spending on it by $50"
        Output: "Cancel Netflix subscription and reduce spending on dining category by $50"
        """
        # 1. Rule-based resolution
        resolved = self._rule_based_resolve(message, context)

        # 2. If ambiguous, use LLM
        if self._has_ambiguous_references(resolved):
            resolved = await self._llm_resolve(resolved, context)

        return ResolvedMessage(
            original=message,
            resolved=resolved,
            substitutions=self._get_substitutions(message, resolved)
        )
```

#### 3.4 Analytics & Optimization

```python
# services/analytics.py

class AgentAnalytics:
    """Track agent performance and user interactions."""

    async def log_interaction(self, event: InteractionEvent) -> None:
        """Log an interaction event."""
        await self.store.insert({
            "timestamp": datetime.utcnow(),
            "user_id": event.user_id,
            "session_id": event.session_id,
            "event_type": event.type,
            "tool_used": event.tool_name,
            "success": event.success,
            "latency_ms": event.latency_ms,
            "user_feedback": event.feedback
        })

    def get_tool_success_rates(self) -> Dict[str, float]:
        """Get success rate by tool."""
        ...

    def get_common_failure_patterns(self) -> List[FailurePattern]:
        """Identify common failure patterns for improvement."""
        ...
```

#### 3.5 Deliverables

| Deliverable | Description |
|-------------|-------------|
| `ProfileHealthEngine` | State condition monitoring |
| `ProactiveManager` | Intervention timing and delivery |
| 7 initial state conditions | Full implementations with checkers |
| `EntityTracker` | Reference resolution system |
| `AgentAnalytics` | Logging and metrics |
| A/B testing framework | Compare agent behaviors |

---

## Appendix A: File Structure

```
BudgetBuddyBackend/
├── app.py                      # Flask entry point
├── db_models.py                # SQLAlchemy models
├── models.py                   # Data transfer objects
│
├── services/
│   ├── __init__.py
│   ├── orchestrator.py         # Updated: uses ReasoningEngine
│   ├── reasoning_engine.py     # NEW: ReAct reasoning loop
│   ├── llm_service.py          # Enhanced LLM wrapper
│   ├── conversation_manager.py # NEW: Session memory
│   ├── state_engine.py         # NEW: Profile health monitor
│   ├── proactive_manager.py    # NEW: Intervention system
│   ├── document_processor.py   # NEW: Multi-modal input
│   ├── reference_resolver.py   # NEW: Anaphora resolution
│   ├── analytics.py            # NEW: Metrics and logging
│   ├── cache.py                # NEW: Cache abstraction
│   │
│   ├── plan_generator.py       # Existing: enhanced
│   └── statement_analyzer.py   # Existing: enhanced
│
├── tools/
│   ├── __init__.py             # Auto-discovery
│   ├── base.py                 # NEW: Tool base classes
│   ├── registry.py             # NEW: Tool registry
│   │
│   ├── budget_overview.py      # Migrated tool
│   ├── spending_status.py      # Migrated tool
│   ├── account_balance.py      # Migrated tool
│   ├── savings_progress.py     # Migrated tool
│   │
│   ├── track_transaction.py    # NEW: Write tool
│   ├── update_budget.py        # NEW: Write tool
│   ├── manage_goals.py         # NEW: Write tool
│   └── statement_parser.py     # NEW: Document tool
│
├── state_conditions/
│   ├── __init__.py
│   ├── critical.py             # Critical state definitions
│   ├── warnings.py             # Warning state definitions
│   └── info.py                 # Info state definitions
│
└── tests/
    ├── test_reasoning_engine.py
    ├── test_tool_registry.py
    ├── test_conversation_manager.py
    ├── test_state_engine.py
    └── test_tools/
        └── ...
```

---

## Appendix B: API Changes

### New Endpoints

```python
# Session management
POST /session/start          # Start conversation session
POST /session/end            # End session, persist context

# Proactive
GET  /proactive/check        # Check for pending interventions
POST /proactive/dismiss      # Dismiss an intervention

# Tools
GET  /tools                  # List available tools
POST /tools/{name}/execute   # Direct tool execution (for debugging)
```

### Updated Endpoints

```python
# Chat - now session-aware
POST /chat
{
    "message": "string",
    "session_id": "string",      # NEW: Session identifier
    "attachments": ["file_id"],  # NEW: Reference uploaded files
    "context_override": {}       # NEW: Explicit context injection
}

# Response structure
{
    "text": "string",
    "visual": {},
    "ui_events": [],             # NEW: Navigation hints
    "suggestions": [],           # NEW: Follow-up suggestions
    "session_id": "string"       # Echo back session
}
```

---

## Appendix C: Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Tool Selection Accuracy | >90% | Correct tool for intent |
| Response Latency (p95) | <3s | End-to-end response time |
| Proactive Acceptance Rate | >40% | Users accepting suggestions |
| Reference Resolution Accuracy | >85% | Correct entity resolution |
| Session Continuity | >80% | Users completing multi-turn flows |
| Feature Discovery | +30% | Users discovering new capabilities |

---

## Conclusion

This architecture transforms BudgetBuddy from a keyword-matching system into a sophisticated AI agent that:

1. **Knows the user deeply** - Through profile health monitoring and contextual awareness
2. **Acts proactively** - Detecting important states and guiding users
3. **Uses tools intelligently** - Via ReAct reasoning and a scalable registry
4. **Remembers context** - Maintaining conversation memory and resolving references
5. **Extends gracefully** - New tools and conditions plug in without core changes

The phased approach ensures incremental value delivery while building toward the complete vision of an AI that **is** the app, not just a feature within it.
