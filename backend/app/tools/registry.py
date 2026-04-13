"""Tool registry — maps Claude tool_use calls to actual functions."""

from __future__ import annotations

import logging
from typing import Any, Callable, Coroutine

log = logging.getLogger("jarvis.tools")

# Tool function type: async (input_dict) -> str
ToolFn = Callable[[dict[str, Any]], Coroutine[Any, Any, str]]

_tools: dict[str, ToolFn] = {}
_schemas: list[dict[str, Any]] = []


def tool(name: str, description: str, input_schema: dict[str, Any]):
    """Decorator to register a tool."""
    def decorator(fn: ToolFn) -> ToolFn:
        _tools[name] = fn
        _schemas.append({
            "name": name,
            "description": description,
            "input_schema": input_schema,
        })
        return fn
    return decorator


def get_tool_schemas() -> list[dict[str, Any]]:
    return _schemas


async def execute_tool(name: str, input_data: dict[str, Any]) -> str:
    fn = _tools.get(name)
    if not fn:
        return f"Unknown tool: {name}"
    try:
        return await fn(input_data)
    except Exception as e:
        log.exception("Tool %s failed", name)
        return f"Tool error: {e}"
