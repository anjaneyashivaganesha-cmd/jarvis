"""Automation chains — chain multiple commands into named routines."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from app.tools.registry import tool, execute_tool

log = logging.getLogger("jarvis.tools.automation")

# Store chains in a JSON file
_CHAINS_FILE = Path(__file__).parent.parent.parent / "db" / "chains.json"


def _load_chains() -> dict[str, list[dict]]:
    if _CHAINS_FILE.exists():
        return json.loads(_CHAINS_FILE.read_text())
    return {}


def _save_chains(chains: dict[str, list[dict]]) -> None:
    _CHAINS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _CHAINS_FILE.write_text(json.dumps(chains, indent=2))


@tool(
    name="create_chain",
    description="Create an automation chain — a named sequence of commands that run together. Use when user says 'create a morning routine', 'make a chain called work mode'. Each step is a tool name + input.",
    input_schema={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Name for the chain (e.g., 'morning', 'work_mode', 'bedtime')"},
            "steps": {
                "type": "array",
                "description": "List of steps. Each step has 'tool' (tool name) and 'input' (tool input dict)",
                "items": {
                    "type": "object",
                    "properties": {
                        "tool": {"type": "string"},
                        "input": {"type": "object"},
                    },
                    "required": ["tool", "input"],
                },
            },
        },
        "required": ["name", "steps"],
    },
)
async def create_chain_tool(input_data: dict[str, Any]) -> str:
    name = input_data["name"].lower().strip().replace(" ", "_")
    steps = input_data["steps"]
    chains = _load_chains()
    chains[name] = steps
    _save_chains(chains)
    step_names = [s["tool"] for s in steps]
    return f"Chain '{name}' created with {len(steps)} steps: {', '.join(step_names)}"


@tool(
    name="run_chain",
    description="Run a saved automation chain by name. Use when user says 'run morning routine', 'start work mode', 'do my bedtime chain'.",
    input_schema={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Name of the chain to run"},
        },
        "required": ["name"],
    },
)
async def run_chain_tool(input_data: dict[str, Any]) -> str:
    name = input_data["name"].lower().strip().replace(" ", "_")
    chains = _load_chains()

    if name not in chains:
        available = ", ".join(chains.keys()) if chains else "none"
        return f"Chain '{name}' not found. Available chains: {available}"

    steps = chains[name]
    results = []
    for i, step in enumerate(steps, 1):
        tool_name = step["tool"]
        tool_input = step.get("input", {})
        log.info("Chain '%s' step %d: %s", name, i, tool_name)
        result = await execute_tool(tool_name, tool_input)
        results.append(f"Step {i} ({tool_name}): {result[:80]}")

    return f"Chain '{name}' completed ({len(steps)} steps):\n" + "\n".join(results)


@tool(
    name="list_chains",
    description="List all saved automation chains. Use when user says 'what chains do I have', 'show my routines'.",
    input_schema={"type": "object", "properties": {}},
)
async def list_chains_tool(input_data: dict[str, Any]) -> str:
    chains = _load_chains()
    if not chains:
        return "No automation chains saved yet. Say 'create a chain called morning' to get started."
    lines = []
    for name, steps in chains.items():
        step_names = [s["tool"] for s in steps]
        lines.append(f"- {name}: {', '.join(step_names)}")
    return f"{len(chains)} chains:\n" + "\n".join(lines)


@tool(
    name="delete_chain",
    description="Delete a saved automation chain.",
    input_schema={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Name of the chain to delete"},
        },
        "required": ["name"],
    },
)
async def delete_chain_tool(input_data: dict[str, Any]) -> str:
    name = input_data["name"].lower().strip().replace(" ", "_")
    chains = _load_chains()
    if name in chains:
        del chains[name]
        _save_chains(chains)
        return f"Chain '{name}' deleted."
    return f"Chain '{name}' not found."
