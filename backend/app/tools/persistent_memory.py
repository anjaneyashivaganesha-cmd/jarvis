"""Persistent memory tools — remember facts across sessions."""

from __future__ import annotations

import logging
from typing import Any

from app.tools.registry import tool
from app import memory

log = logging.getLogger("jarvis.tools.memory")


@tool(
    name="remember_this",
    description="Save a fact or piece of information to persistent memory. Survives across sessions. Use when user says 'remember that...', 'save this info', 'don't forget that...'.",
    input_schema={
        "type": "object",
        "properties": {
            "fact": {"type": "string", "description": "The fact or information to remember"},
            "category": {"type": "string", "description": "Category: 'personal', 'work', 'preference', 'technical', or 'general'"},
        },
        "required": ["fact"],
    },
)
async def remember_tool(input_data: dict[str, Any]) -> str:
    fact = input_data["fact"]
    category = input_data.get("category", "general")
    fact_id = await memory.remember_fact(fact, category)
    if fact_id > 0:
        return f"Got it, I'll remember that. (Saved as fact #{fact_id})"
    return "Sorry, I couldn't save that to memory."


@tool(
    name="recall",
    description="Search persistent memory for something you were told to remember. Use when user says 'what did I tell you about...', 'do you remember...', 'what do you know about...'.",
    input_schema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "What to search for in memory"},
        },
        "required": ["query"],
    },
)
async def recall_tool(input_data: dict[str, Any]) -> str:
    query = input_data["query"]
    facts = await memory.recall_facts(query)
    if facts:
        lines = [f"- {f['fact']} ({f['category']})" for f in facts]
        return f"I remember {len(facts)} thing(s):\n" + "\n".join(lines)
    return f"I don't have anything saved about '{query}'."


@tool(
    name="list_memories",
    description="Show all saved memories/facts. Use when user says 'what do you remember', 'show all memories'.",
    input_schema={"type": "object", "properties": {}},
)
async def list_memories_tool(input_data: dict[str, Any]) -> str:
    facts = await memory.get_all_facts(limit=20)
    if facts:
        lines = [f"#{f['id']}: {f['fact']} [{f['category']}]" for f in facts]
        return f"{len(facts)} memories:\n" + "\n".join(lines)
    return "No memories saved yet. Tell me something to remember!"


@tool(
    name="forget",
    description="Remove a specific memory by its ID number. Use when user says 'forget #5', 'delete that memory'.",
    input_schema={
        "type": "object",
        "properties": {
            "fact_id": {"type": "integer", "description": "The memory ID number to forget"},
        },
        "required": ["fact_id"],
    },
)
async def forget_tool(input_data: dict[str, Any]) -> str:
    fact_id = input_data["fact_id"]
    if await memory.forget_fact(fact_id):
        return f"Memory #{fact_id} forgotten."
    return f"Memory #{fact_id} not found."
