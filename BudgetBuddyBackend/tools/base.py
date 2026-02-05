"""
Base classes and schemas for the BudgetBuddy Tool System.
Provides a declarative framework for defining, validating, and executing tools.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import (
    Any, Callable, Dict, List, Literal, Optional, Union, TypeVar, Generic
)
import json
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# ENUMS AND CONSTANTS
# =============================================================================

class ToolCategory(str, Enum):
    """Categories for organizing tools."""
    ANALYSIS = "analysis"
    PLANNING = "planning"
    TRACKING = "tracking"
    DOCUMENT_PROCESSING = "document_processing"
    ACCOUNT_MANAGEMENT = "account_management"
    NOTIFICATIONS = "notifications"


class Severity(str, Enum):
    """Severity levels for conditions and alerts."""
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


# =============================================================================
# TOOL PARAMETER DEFINITIONS
# =============================================================================

@dataclass
class ToolParameter:
    """
    Defines a single parameter for a tool.
    Used to generate JSON schemas and validate inputs.
    """
    name: str
    type: Literal["string", "number", "integer", "boolean", "array", "object"]
    description: str
    required: bool = True
    default: Any = None
    enum: Optional[List[Any]] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    items_type: Optional[str] = None  # For array types

    def to_json_schema(self) -> Dict[str, Any]:
        """Convert to JSON Schema format."""
        schema: Dict[str, Any] = {
            "type": self.type,
            "description": self.description
        }

        if self.enum:
            schema["enum"] = self.enum
        if self.min_value is not None:
            schema["minimum"] = self.min_value
        if self.max_value is not None:
            schema["maximum"] = self.max_value
        if self.min_length is not None:
            schema["minLength"] = self.min_length
        if self.max_length is not None:
            schema["maxLength"] = self.max_length
        if self.type == "array" and self.items_type:
            schema["items"] = {"type": self.items_type}
        if self.default is not None:
            schema["default"] = self.default

        return schema


# =============================================================================
# TOOL DEFINITION
# =============================================================================

@dataclass
class ToolDefinition:
    """
    Complete specification of a tool's interface and behavior.
    This is the declarative schema that describes what a tool does.
    """

    # Identity
    name: str
    display_name: str
    category: ToolCategory
    version: str = "1.0.0"

    # LLM Interface - descriptions for the model
    description: str = ""
    when_to_use: str = ""
    when_not_to_use: str = ""
    example_triggers: List[str] = field(default_factory=list)

    # Parameters
    parameters: List[ToolParameter] = field(default_factory=list)
    returns_schema: Dict[str, Any] = field(default_factory=dict)

    # Capabilities and requirements
    requires: List[str] = field(default_factory=list)  # Prerequisites
    produces: List[str] = field(default_factory=list)  # Outputs

    # Safety and side effects
    side_effects: List[str] = field(default_factory=list)
    confirmation_required: bool = False
    is_destructive: bool = False

    # Execution settings
    timeout_seconds: int = 30
    max_retries: int = 0

    # Visual output
    visual_type: Optional[str] = None  # "sankeyFlow", "burndownChart", etc.

    def to_openai_schema(self) -> Dict[str, Any]:
        """Convert to OpenAI function calling format."""
        # Build parameter properties
        properties = {}
        required = []

        for param in self.parameters:
            properties[param.name] = param.to_json_schema()
            if param.required:
                required.append(param.name)

        # Build full description with usage guidance
        full_description = self.description
        if self.when_to_use:
            full_description += f"\n\nWHEN TO USE: {self.when_to_use}"
        if self.when_not_to_use:
            full_description += f"\n\nWHEN NOT TO USE: {self.when_not_to_use}"

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": full_description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required
                }
            }
        }


# =============================================================================
# TOOL CONTEXT
# =============================================================================

@dataclass
class ToolContext:
    """
    Runtime context passed to tool execution.
    Contains all the information a tool needs to execute.
    """
    user_id: int
    session_id: Optional[str] = None
    params: Dict[str, Any] = field(default_factory=dict)

    # User state flags
    is_authenticated: bool = True
    has_profile: bool = False
    has_plan: bool = False
    has_statement: bool = False

    # Pending resources
    pending_files: List[str] = field(default_factory=list)
    user_confirmed: bool = False

    # Database session (injected at runtime)
    db: Any = None

    # LLM service (injected at runtime)
    llm: Any = None

    # Event emitter for UI events
    events: List[Dict[str, Any]] = field(default_factory=list)

    def with_params(self, params: Dict[str, Any]) -> 'ToolContext':
        """Create a new context with updated parameters."""
        return ToolContext(
            user_id=self.user_id,
            session_id=self.session_id,
            params=params,
            is_authenticated=self.is_authenticated,
            has_profile=self.has_profile,
            has_plan=self.has_plan,
            has_statement=self.has_statement,
            pending_files=self.pending_files,
            user_confirmed=self.user_confirmed,
            db=self.db,
            llm=self.llm,
            events=self.events
        )

    def emit_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """Emit a UI event."""
        self.events.append({
            "type": event_type,
            "data": data,
            "timestamp": datetime.utcnow().isoformat()
        })

    def has_uploaded_file(self, file_id: str) -> bool:
        """Check if a file has been uploaded."""
        return file_id in self.pending_files


# =============================================================================
# TOOL RESULT
# =============================================================================

@dataclass
class ToolResult:
    """
    Result returned from tool execution.
    Contains data, visual payload, and execution metadata.
    """
    success: bool
    data: Dict[str, Any] = field(default_factory=dict)
    message: str = ""
    visual: Optional[Dict[str, Any]] = None
    ui_events: List[Dict[str, Any]] = field(default_factory=list)
    follow_up_suggestions: List[str] = field(default_factory=list)

    # For confirmation flows
    needs_confirmation: bool = False
    confirmation_message: str = ""
    pending_tool_name: str = ""
    pending_params: Dict[str, Any] = field(default_factory=dict)

    # Error info
    error: Optional[str] = None
    error_code: Optional[str] = None

    @classmethod
    def success_result(
        cls,
        data: Dict[str, Any],
        message: str = "",
        visual: Optional[Dict[str, Any]] = None,
        suggestions: Optional[List[str]] = None
    ) -> 'ToolResult':
        """Create a successful result."""
        return cls(
            success=True,
            data=data,
            message=message,
            visual=visual,
            follow_up_suggestions=suggestions or []
        )

    @classmethod
    def error_result(
        cls,
        error: str,
        error_code: Optional[str] = None
    ) -> 'ToolResult':
        """Create an error result."""
        return cls(
            success=False,
            error=error,
            error_code=error_code,
            message=f"Error: {error}"
        )

    @classmethod
    def confirmation_required(
        cls,
        message: str,
        tool_name: str,
        params: Dict[str, Any]
    ) -> 'ToolResult':
        """Create a result that requires user confirmation."""
        return cls(
            success=True,
            needs_confirmation=True,
            confirmation_message=message,
            pending_tool_name=tool_name,
            pending_params=params,
            message=message
        )


# =============================================================================
# VALIDATION
# =============================================================================

@dataclass
class ValidationResult:
    """Result of parameter validation."""
    valid: bool
    errors: List[str] = field(default_factory=list)


class ParameterValidator:
    """Validates tool parameters against their definitions."""

    @staticmethod
    def validate(
        params: Dict[str, Any],
        parameter_defs: List[ToolParameter]
    ) -> ValidationResult:
        """Validate parameters against definitions."""
        errors = []

        # Build lookup of parameter definitions
        param_lookup = {p.name: p for p in parameter_defs}

        # Check required parameters
        for param_def in parameter_defs:
            if param_def.required and param_def.name not in params:
                if param_def.default is None:
                    errors.append(f"Missing required parameter: {param_def.name}")

        # Validate provided parameters
        for name, value in params.items():
            if name not in param_lookup:
                errors.append(f"Unknown parameter: {name}")
                continue

            param_def = param_lookup[name]
            param_errors = ParameterValidator._validate_value(value, param_def)
            errors.extend(param_errors)

        return ValidationResult(valid=len(errors) == 0, errors=errors)

    @staticmethod
    def _validate_value(value: Any, param_def: ToolParameter) -> List[str]:
        """Validate a single parameter value."""
        errors = []

        # Type checking
        type_checks = {
            "string": lambda v: isinstance(v, str),
            "number": lambda v: isinstance(v, (int, float)),
            "integer": lambda v: isinstance(v, int),
            "boolean": lambda v: isinstance(v, bool),
            "array": lambda v: isinstance(v, list),
            "object": lambda v: isinstance(v, dict),
        }

        if param_def.type in type_checks:
            if not type_checks[param_def.type](value):
                errors.append(
                    f"Parameter '{param_def.name}' must be of type {param_def.type}"
                )
                return errors  # Skip further validation if type is wrong

        # Enum validation
        if param_def.enum and value not in param_def.enum:
            errors.append(
                f"Parameter '{param_def.name}' must be one of: {param_def.enum}"
            )

        # Numeric range validation
        if param_def.type in ("number", "integer"):
            if param_def.min_value is not None and value < param_def.min_value:
                errors.append(
                    f"Parameter '{param_def.name}' must be >= {param_def.min_value}"
                )
            if param_def.max_value is not None and value > param_def.max_value:
                errors.append(
                    f"Parameter '{param_def.name}' must be <= {param_def.max_value}"
                )

        # String length validation
        if param_def.type == "string":
            if param_def.min_length is not None and len(value) < param_def.min_length:
                errors.append(
                    f"Parameter '{param_def.name}' must have length >= {param_def.min_length}"
                )
            if param_def.max_length is not None and len(value) > param_def.max_length:
                errors.append(
                    f"Parameter '{param_def.name}' must have length <= {param_def.max_length}"
                )

        return errors


# =============================================================================
# BASE TOOL CLASS
# =============================================================================

class Tool(ABC):
    """
    Abstract base class for all tools.
    Subclasses must define a `definition` and implement `execute`.
    """

    # Subclasses must set this
    definition: ToolDefinition

    def validate_params(self, params: Dict[str, Any]) -> ValidationResult:
        """Validate parameters against the tool's definition."""
        return ParameterValidator.validate(params, self.definition.parameters)

    @abstractmethod
    async def execute(self, context: ToolContext) -> ToolResult:
        """
        Execute the tool with the given context.

        Args:
            context: ToolContext containing user info, params, and services

        Returns:
            ToolResult with data, visual payload, and metadata
        """
        pass

    def get_openai_schema(self) -> Dict[str, Any]:
        """Get the OpenAI function schema for this tool."""
        return self.definition.to_openai_schema()


# =============================================================================
# TOOL HOOKS
# =============================================================================

class ToolHook(ABC):
    """
    Abstract base class for tool execution hooks.
    Hooks can observe and modify tool execution.
    """

    @abstractmethod
    async def before_execute(
        self,
        tool: Tool,
        params: Dict[str, Any],
        context: ToolContext
    ) -> None:
        """Called before tool execution."""
        pass

    @abstractmethod
    async def after_execute(
        self,
        tool: Tool,
        params: Dict[str, Any],
        context: ToolContext,
        result: ToolResult
    ) -> None:
        """Called after tool execution."""
        pass


class LoggingHook(ToolHook):
    """Hook that logs tool executions."""

    async def before_execute(
        self,
        tool: Tool,
        params: Dict[str, Any],
        context: ToolContext
    ) -> None:
        logger.info(
            f"Executing tool: {tool.definition.name} "
            f"for user {context.user_id} "
            f"with params: {params}"
        )

    async def after_execute(
        self,
        tool: Tool,
        params: Dict[str, Any],
        context: ToolContext,
        result: ToolResult
    ) -> None:
        status = "success" if result.success else "failed"
        logger.info(
            f"Tool {tool.definition.name} {status} "
            f"for user {context.user_id}"
        )
        if not result.success:
            logger.error(f"Tool error: {result.error}")


class AnalyticsHook(ToolHook):
    """Hook that records tool usage analytics."""

    def __init__(self):
        self.executions: List[Dict[str, Any]] = []

    async def before_execute(
        self,
        tool: Tool,
        params: Dict[str, Any],
        context: ToolContext
    ) -> None:
        pass

    async def after_execute(
        self,
        tool: Tool,
        params: Dict[str, Any],
        context: ToolContext,
        result: ToolResult
    ) -> None:
        self.executions.append({
            "tool_name": tool.definition.name,
            "user_id": context.user_id,
            "session_id": context.session_id,
            "success": result.success,
            "timestamp": datetime.utcnow().isoformat(),
            "has_visual": result.visual is not None
        })
