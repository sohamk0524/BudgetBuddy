"""
BudgetBuddy Tool System.

This package provides the tool infrastructure for the AI agent:
- Base classes for defining tools (Tool, ToolDefinition, ToolParameter)
- Tool registry for discovery and execution
- Built-in tools for financial operations

Usage:
    from tools import get_default_registry, ToolContext

    # Get the registry
    registry = get_default_registry()

    # Create context
    context = ToolContext(user_id=1, has_profile=True)

    # Execute a tool
    result = await registry.execute("get_budget_overview", {}, context)
"""

from tools.base import (
    Tool,
    ToolDefinition,
    ToolParameter,
    ToolContext,
    ToolResult,
    ToolCategory,
    ToolHook,
    LoggingHook,
    AnalyticsHook,
    ValidationResult,
    ParameterValidator,
    Severity,
)

from tools.registry import (
    ToolRegistry,
    create_tool_registry,
    get_default_registry,
    reset_default_registry,
    discover_tools,
)

__all__ = [
    # Base classes
    "Tool",
    "ToolDefinition",
    "ToolParameter",
    "ToolContext",
    "ToolResult",
    "ToolCategory",
    "ToolHook",
    "LoggingHook",
    "AnalyticsHook",
    "ValidationResult",
    "ParameterValidator",
    "Severity",
    # Registry
    "ToolRegistry",
    "create_tool_registry",
    "get_default_registry",
    "reset_default_registry",
    "discover_tools",
]
