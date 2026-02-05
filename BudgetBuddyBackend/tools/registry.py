"""
Tool Registry for BudgetBuddy.
Central registry for all available tools with discovery, validation, and execution.
"""

import asyncio
import importlib
import inspect
import logging
import pkgutil
from collections import defaultdict
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Type

from tools.base import (
    Tool,
    ToolContext,
    ToolDefinition,
    ToolHook,
    ToolResult,
    LoggingHook,
    AnalyticsHook,
)

logger = logging.getLogger(__name__)


class ToolRegistry:
    """
    Central registry for all available tools.
    Handles registration, discovery, prerequisite checking, and execution.
    """

    def __init__(self):
        self._tools: Dict[str, Tool] = {}
        self._categories: Dict[str, List[str]] = defaultdict(list)
        self._hooks: List[ToolHook] = []
        self._execution_history: List[Dict[str, Any]] = []

    def register(self, tool: Tool) -> None:
        """
        Register a tool in the registry.

        Args:
            tool: Tool instance to register

        Raises:
            ValueError: If tool with same name already registered
        """
        name = tool.definition.name
        if name in self._tools:
            raise ValueError(f"Tool '{name}' is already registered")

        self._tools[name] = tool
        self._categories[tool.definition.category.value].append(name)
        logger.info(f"Registered tool: {name} (category: {tool.definition.category.value})")

    def register_hook(self, hook: ToolHook) -> None:
        """Register a hook for tool execution events."""
        self._hooks.append(hook)
        logger.info(f"Registered hook: {hook.__class__.__name__}")

    def unregister(self, name: str) -> bool:
        """
        Unregister a tool by name.

        Returns:
            True if tool was found and removed, False otherwise
        """
        if name not in self._tools:
            return False

        tool = self._tools[name]
        category = tool.definition.category.value
        self._categories[category].remove(name)
        del self._tools[name]
        logger.info(f"Unregistered tool: {name}")
        return True

    def get(self, name: str) -> Optional[Tool]:
        """Get a tool by name."""
        return self._tools.get(name)

    def get_all(self) -> List[Tool]:
        """Get all registered tools."""
        return list(self._tools.values())

    def get_by_category(self, category: str) -> List[Tool]:
        """Get all tools in a category."""
        tool_names = self._categories.get(category, [])
        return [self._tools[name] for name in tool_names]

    def get_available_tools(self, context: ToolContext) -> List[Tool]:
        """
        Get tools available given current context (respecting prerequisites).

        Args:
            context: Current tool context with user state

        Returns:
            List of tools whose prerequisites are satisfied
        """
        available = []
        for tool in self._tools.values():
            if self._check_prerequisites(tool, context):
                available.append(tool)
        return available

    def get_openai_schemas(self, context: Optional[ToolContext] = None) -> List[Dict[str, Any]]:
        """
        Get OpenAI function schemas for available tools.

        Args:
            context: Optional context to filter by prerequisites

        Returns:
            List of OpenAI-compatible function definitions
        """
        if context:
            tools = self.get_available_tools(context)
        else:
            tools = self.get_all()

        return [tool.get_openai_schema() for tool in tools]

    async def execute(
        self,
        name: str,
        params: Dict[str, Any],
        context: ToolContext
    ) -> ToolResult:
        """
        Execute a tool with full lifecycle management.

        Args:
            name: Tool name to execute
            params: Parameters for the tool
            context: Execution context

        Returns:
            ToolResult with execution outcome
        """
        start_time = datetime.utcnow()

        # Get the tool
        tool = self.get(name)
        if not tool:
            return ToolResult.error_result(f"Unknown tool: {name}", "UNKNOWN_TOOL")

        # Pre-execution hooks
        for hook in self._hooks:
            try:
                await hook.before_execute(tool, params, context)
            except Exception as e:
                logger.warning(f"Hook before_execute failed: {e}")

        # Validate prerequisites
        if not self._check_prerequisites(tool, context):
            missing = self._get_missing_prerequisites(tool, context)
            return ToolResult.error_result(
                f"Prerequisites not met: {', '.join(missing)}",
                "PREREQUISITES_NOT_MET"
            )

        # Validate parameters
        validation = tool.validate_params(params)
        if not validation.valid:
            return ToolResult.error_result(
                f"Invalid parameters: {'; '.join(validation.errors)}",
                "INVALID_PARAMS"
            )

        # Check confirmation requirement
        if tool.definition.confirmation_required and not context.user_confirmed:
            effects = tool.definition.side_effects or ["make changes"]
            effects_str = ", ".join(effects)
            return ToolResult.confirmation_required(
                message=f"This action will {effects_str}. Do you want to proceed?",
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
            result = ToolResult.error_result(
                f"Tool execution timed out after {tool.definition.timeout_seconds}s",
                "TIMEOUT"
            )
        except Exception as e:
            logger.exception(f"Tool {name} execution failed")
            result = ToolResult.error_result(
                f"Tool execution failed: {str(e)}",
                "EXECUTION_ERROR"
            )

        # Record execution
        end_time = datetime.utcnow()
        self._record_execution(
            tool_name=name,
            user_id=context.user_id,
            session_id=context.session_id,
            success=result.success,
            duration_ms=(end_time - start_time).total_seconds() * 1000,
            error=result.error
        )

        # Post-execution hooks
        for hook in self._hooks:
            try:
                await hook.after_execute(tool, params, context, result)
            except Exception as e:
                logger.warning(f"Hook after_execute failed: {e}")

        return result

    def execute_sync(
        self,
        name: str,
        params: Dict[str, Any],
        context: ToolContext
    ) -> ToolResult:
        """
        Synchronous wrapper for execute.
        Creates a new event loop if needed.
        """
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If we're already in an async context, we need a different approach
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(
                        asyncio.run,
                        self.execute(name, params, context)
                    )
                    return future.result()
            else:
                return loop.run_until_complete(
                    self.execute(name, params, context)
                )
        except RuntimeError:
            # No event loop, create one
            return asyncio.run(self.execute(name, params, context))

    def _check_prerequisites(self, tool: Tool, context: ToolContext) -> bool:
        """Check if all prerequisites for a tool are met."""
        for req in tool.definition.requires:
            if req == "authenticated" and not context.is_authenticated:
                return False
            if req == "has_profile" and not context.has_profile:
                return False
            if req == "has_plan" and not context.has_plan:
                return False
            if req == "has_statement" and not context.has_statement:
                return False
            if req == "file_uploaded" and not context.pending_files:
                return False
        return True

    def _get_missing_prerequisites(self, tool: Tool, context: ToolContext) -> List[str]:
        """Get list of prerequisites that are not met."""
        missing = []
        prereq_checks = {
            "authenticated": context.is_authenticated,
            "has_profile": context.has_profile,
            "has_plan": context.has_plan,
            "has_statement": context.has_statement,
            "file_uploaded": bool(context.pending_files),
        }

        for req in tool.definition.requires:
            if req in prereq_checks and not prereq_checks[req]:
                missing.append(req)

        return missing

    def _record_execution(
        self,
        tool_name: str,
        user_id: int,
        session_id: Optional[str],
        success: bool,
        duration_ms: float,
        error: Optional[str]
    ) -> None:
        """Record tool execution for analytics."""
        self._execution_history.append({
            "tool_name": tool_name,
            "user_id": user_id,
            "session_id": session_id,
            "success": success,
            "duration_ms": duration_ms,
            "error": error,
            "timestamp": datetime.utcnow().isoformat()
        })

        # Keep only last 1000 executions in memory
        if len(self._execution_history) > 1000:
            self._execution_history = self._execution_history[-1000:]

    def get_execution_stats(self) -> Dict[str, Any]:
        """Get execution statistics."""
        if not self._execution_history:
            return {"total_executions": 0}

        total = len(self._execution_history)
        successful = sum(1 for e in self._execution_history if e["success"])

        # Per-tool stats
        tool_stats = defaultdict(lambda: {"total": 0, "success": 0, "avg_duration_ms": 0})
        for execution in self._execution_history:
            name = execution["tool_name"]
            tool_stats[name]["total"] += 1
            if execution["success"]:
                tool_stats[name]["success"] += 1
            tool_stats[name]["avg_duration_ms"] += execution["duration_ms"]

        for name in tool_stats:
            total_for_tool = tool_stats[name]["total"]
            tool_stats[name]["avg_duration_ms"] /= total_for_tool
            tool_stats[name]["success_rate"] = tool_stats[name]["success"] / total_for_tool

        return {
            "total_executions": total,
            "success_rate": successful / total if total > 0 else 0,
            "per_tool": dict(tool_stats)
        }


def discover_tools(package_name: str = "tools") -> List[Type[Tool]]:
    """
    Auto-discover Tool subclasses in a package.

    Args:
        package_name: Name of the package to scan

    Returns:
        List of Tool subclasses found
    """
    discovered: List[Type[Tool]] = []

    try:
        package = importlib.import_module(package_name)
    except ImportError:
        logger.warning(f"Could not import package: {package_name}")
        return discovered

    # Get the package path
    if hasattr(package, "__path__"):
        package_path = package.__path__
    else:
        return discovered

    # Iterate through modules in the package
    for _, module_name, _ in pkgutil.iter_modules(package_path):
        if module_name.startswith("_"):
            continue

        try:
            module = importlib.import_module(f"{package_name}.{module_name}")

            # Find Tool subclasses in the module
            for name, obj in inspect.getmembers(module, inspect.isclass):
                if (
                    issubclass(obj, Tool)
                    and obj is not Tool
                    and hasattr(obj, "definition")
                ):
                    discovered.append(obj)
                    logger.debug(f"Discovered tool class: {name}")

        except ImportError as e:
            logger.warning(f"Could not import module {module_name}: {e}")

    return discovered


def create_tool_registry(auto_discover: bool = True) -> ToolRegistry:
    """
    Create and populate the tool registry.

    Args:
        auto_discover: Whether to auto-discover tools from the tools package

    Returns:
        Configured ToolRegistry instance
    """
    registry = ToolRegistry()

    # Register hooks
    registry.register_hook(LoggingHook())
    registry.register_hook(AnalyticsHook())

    # Auto-discover and register tools
    if auto_discover:
        tool_classes = discover_tools("tools")
        for tool_class in tool_classes:
            try:
                tool_instance = tool_class()
                registry.register(tool_instance)
            except Exception as e:
                logger.error(f"Failed to instantiate {tool_class.__name__}: {e}")

    return registry


# Singleton registry instance
_default_registry: Optional[ToolRegistry] = None


def get_default_registry() -> ToolRegistry:
    """Get the default tool registry instance."""
    global _default_registry
    if _default_registry is None:
        _default_registry = create_tool_registry()
    return _default_registry


def reset_default_registry() -> None:
    """Reset the default registry (useful for testing)."""
    global _default_registry
    _default_registry = None
