"""Notes tool — CRUD operations on notes via SQLite."""

from __future__ import annotations

import json
from typing import Any

from app.memory import create_note, delete_note, get_notes, search_notes
from app.tools.registry import tool


@tool(
    name="create_note",
    description="Create a new note with a title and body. Use when the user wants to save information, make a reminder, or jot something down.",
    input_schema={
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Short title for the note"},
            "body": {"type": "string", "description": "The note content"},
        },
        "required": ["title", "body"],
    },
)
async def create_note_tool(input_data: dict[str, Any]) -> str:
    note_id = await create_note(input_data["title"], input_data["body"])
    return f"Note created with ID {note_id}: {input_data['title']}"


@tool(
    name="list_notes",
    description="List recent notes. Use when the user asks to see their notes.",
    input_schema={
        "type": "object",
        "properties": {
            "limit": {"type": "integer", "description": "Max notes to return", "default": 10},
        },
    },
)
async def list_notes_tool(input_data: dict[str, Any]) -> str:
    notes = await get_notes(input_data.get("limit", 10))
    if not notes:
        return "No notes found."
    lines = [f"- [{n['id']}] {n['title']}: {n['body'][:80]}" for n in notes]
    return "\n".join(lines)


@tool(
    name="search_notes",
    description="Search notes by keyword. Use when the user asks to find a specific note.",
    input_schema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query"},
        },
        "required": ["query"],
    },
)
async def search_notes_tool(input_data: dict[str, Any]) -> str:
    results = await search_notes(input_data["query"])
    if not results:
        return "No matching notes found."
    lines = [f"- [{n['id']}] {n['title']}: {n['body'][:80]}" for n in results]
    return "\n".join(lines)


@tool(
    name="delete_note",
    description="Delete a note by its ID.",
    input_schema={
        "type": "object",
        "properties": {
            "note_id": {"type": "integer", "description": "The ID of the note to delete"},
        },
        "required": ["note_id"],
    },
)
async def delete_note_tool(input_data: dict[str, Any]) -> str:
    success = await delete_note(input_data["note_id"])
    return "Note deleted." if success else "Note not found."
