"""Productivity tools — calculator, timer, reminders, clipboard, todo."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

from app.tools.registry import tool
from app.tools.system import run_powershell

log = logging.getLogger("jarvis.tools.productivity")

# In-memory storage for timers and reminders
_timers: list[dict] = []
_reminders: list[dict] = []
_todos: list[dict] = []


@tool(
    name="calculate",
    description="Evaluate a math expression. Use for any calculation like '15% of 2400', 'sqrt(144)', '2^10'.",
    input_schema={
        "type": "object",
        "properties": {
            "expression": {"type": "string", "description": "Math expression like '15/100 * 2400' or '2**10'"},
        },
        "required": ["expression"],
    },
)
async def calculate_tool(input_data: dict[str, Any]) -> str:
    expr = input_data["expression"]
    # Safe math evaluation
    import math
    allowed = {
        "abs": abs, "round": round, "min": min, "max": max,
        "sqrt": math.sqrt, "sin": math.sin, "cos": math.cos,
        "tan": math.tan, "log": math.log, "log10": math.log10,
        "pi": math.pi, "e": math.e, "pow": pow, "ceil": math.ceil,
        "floor": math.floor,
    }
    try:
        result = eval(expr, {"__builtins__": {}}, allowed)
        return f"{expr} = {result}"
    except Exception as e:
        return f"Could not calculate: {e}"


@tool(
    name="set_timer",
    description="Set a timer for a number of minutes. When time is up, a notification will appear.",
    input_schema={
        "type": "object",
        "properties": {
            "minutes": {"type": "number", "description": "Timer duration in minutes"},
            "label": {"type": "string", "description": "What the timer is for", "default": "Timer"},
        },
        "required": ["minutes"],
    },
)
async def set_timer_tool(input_data: dict[str, Any]) -> str:
    minutes = input_data["minutes"]
    label = input_data.get("label", "Timer")
    seconds = int(minutes * 60)

    async def _timer():
        await asyncio.sleep(seconds)
        # Show Windows notification
        script = f"""
        [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
        $template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
        $textNodes = $template.GetElementsByTagName('text')
        $textNodes.Item(0).AppendChild($template.CreateTextNode('JARVIS Timer')) > $null
        $textNodes.Item(1).AppendChild($template.CreateTextNode('{label} - Time is up!')) > $null
        $toast = [Windows.UI.Notifications.ToastNotification]::new($template)
        [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('JARVIS').Show($toast)
        """
        await run_powershell(script)

    asyncio.create_task(_timer())
    _timers.append({"label": label, "minutes": minutes, "set_at": datetime.now().isoformat()})
    return f"Timer set for {minutes} minutes: {label}"


@tool(
    name="set_reminder",
    description="Set a reminder at a specific time or after a delay. Example: 'remind me to eat in 1 hour'.",
    input_schema={
        "type": "object",
        "properties": {
            "message": {"type": "string", "description": "What to remind about"},
            "minutes_from_now": {"type": "number", "description": "Minutes from now to remind"},
        },
        "required": ["message", "minutes_from_now"],
    },
)
async def set_reminder_tool(input_data: dict[str, Any]) -> str:
    message = input_data["message"]
    minutes = input_data["minutes_from_now"]
    remind_at = datetime.now() + timedelta(minutes=minutes)

    async def _remind():
        await asyncio.sleep(int(minutes * 60))
        script = f"""
        Add-Type -AssemblyName System.Windows.Forms
        [System.Windows.Forms.MessageBox]::Show('{message}', 'JARVIS Reminder', 'OK', 'Information')
        """
        await run_powershell(script)

    asyncio.create_task(_remind())
    _reminders.append({"message": message, "remind_at": remind_at.strftime("%I:%M %p")})
    return f"Reminder set for {remind_at.strftime('%I:%M %p')}: {message}"


@tool(
    name="clipboard_read",
    description="Read the current contents of the clipboard.",
    input_schema={"type": "object", "properties": {}},
)
async def clipboard_read_tool(input_data: dict[str, Any]) -> str:
    script = "Get-Clipboard"
    result = await run_powershell(script)
    return f"Clipboard contains: {result[:500]}" if result else "Clipboard is empty."


@tool(
    name="clipboard_write",
    description="Copy text to the clipboard.",
    input_schema={
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "Text to copy to clipboard"},
        },
        "required": ["text"],
    },
)
async def clipboard_write_tool(input_data: dict[str, Any]) -> str:
    text = input_data["text"].replace("'", "''")
    script = f"Set-Clipboard -Value '{text}'"
    await run_powershell(script)
    return f"Copied to clipboard: {text[:100]}"


@tool(
    name="add_todo",
    description="Add an item to the todo list.",
    input_schema={
        "type": "object",
        "properties": {
            "task": {"type": "string", "description": "The task to add"},
        },
        "required": ["task"],
    },
)
async def add_todo_tool(input_data: dict[str, Any]) -> str:
    task = input_data["task"]
    _todos.append({"task": task, "done": False, "added": datetime.now().strftime("%I:%M %p")})
    return f"Added to todo list: {task} (#{len(_todos)})"


@tool(
    name="list_todos",
    description="Show all items on the todo list.",
    input_schema={"type": "object", "properties": {}},
)
async def list_todos_tool(input_data: dict[str, Any]) -> str:
    if not _todos:
        return "Your todo list is empty."
    lines = []
    for i, t in enumerate(_todos, 1):
        status = "done" if t["done"] else "pending"
        lines.append(f"{i}. [{status}] {t['task']}")
    return "\n".join(lines)


@tool(
    name="complete_todo",
    description="Mark a todo item as done by its number.",
    input_schema={
        "type": "object",
        "properties": {
            "number": {"type": "integer", "description": "Todo item number to complete"},
        },
        "required": ["number"],
    },
)
async def complete_todo_tool(input_data: dict[str, Any]) -> str:
    idx = input_data["number"] - 1
    if 0 <= idx < len(_todos):
        _todos[idx]["done"] = True
        return f"Marked as done: {_todos[idx]['task']}"
    return "Invalid todo number."


@tool(
    name="daily_briefing",
    description="Give a daily briefing with time, date, pending todos, and reminders. Use when user says 'good morning' or 'daily briefing'.",
    input_schema={"type": "object", "properties": {}},
)
async def daily_briefing_tool(input_data: dict[str, Any]) -> str:
    now = datetime.now()
    greeting = "Good morning" if now.hour < 12 else "Good afternoon" if now.hour < 17 else "Good evening"
    date_str = now.strftime("%A, %B %d, %Y")
    time_str = now.strftime("%I:%M %p")

    parts = [f"{greeting}, sir. It's {date_str} at {time_str}."]

    pending = [t for t in _todos if not t["done"]]
    if pending:
        parts.append(f"You have {len(pending)} pending tasks:")
        for i, t in enumerate(pending, 1):
            parts.append(f"  {i}. {t['task']}")
    else:
        parts.append("No pending tasks.")

    if _reminders:
        parts.append(f"{len(_reminders)} active reminders.")

    return "\n".join(parts)
