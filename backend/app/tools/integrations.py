"""Integration tools — Gmail, Calendar, WhatsApp, Telegram, Notion.
These require API keys/tokens to be configured in .env file.
"""

from __future__ import annotations

import logging
from typing import Any

from app.tools.registry import tool
from app.tools.system import run_powershell

log = logging.getLogger("jarvis.tools.integrations")


# ============================================================
# WHATSAPP (via browser automation — works without API)
# ============================================================

@tool(
    name="send_whatsapp",
    description="Send a WhatsApp message by opening WhatsApp Web. Use when user says 'send a WhatsApp to Mom', 'message John on WhatsApp'.",
    input_schema={
        "type": "object",
        "properties": {
            "phone": {"type": "string", "description": "Phone number with country code (e.g., '+919876543210') or contact name"},
            "message": {"type": "string", "description": "The message to send"},
        },
        "required": ["phone", "message"],
    },
)
async def send_whatsapp_tool(input_data: dict[str, Any]) -> str:
    phone = input_data["phone"].replace(" ", "").replace("-", "")
    message = input_data["message"].replace(" ", "%20")
    # Open WhatsApp Web with pre-filled message
    url = f"https://wa.me/{phone}?text={message}"
    await run_powershell(f"Start-Process '{url}'")
    return f"Opened WhatsApp with message ready to send. Click Send in WhatsApp to complete."


# ============================================================
# TELEGRAM (opens in browser — bot mode needs token in .env)
# ============================================================

@tool(
    name="open_telegram",
    description="Open Telegram Web or send a message via Telegram. Use when user says 'open Telegram', 'message on Telegram'.",
    input_schema={
        "type": "object",
        "properties": {
            "action": {"type": "string", "description": "'open' to open Telegram Web, 'message' to send (needs username)"},
            "username": {"type": "string", "description": "Telegram username to message (without @)"},
            "message": {"type": "string", "description": "Message text"},
        },
        "required": ["action"],
    },
)
async def telegram_tool(input_data: dict[str, Any]) -> str:
    action = input_data["action"].lower()
    if action == "open":
        await run_powershell("Start-Process 'https://web.telegram.org'")
        return "Opened Telegram Web."
    elif action == "message":
        username = input_data.get("username", "")
        if username:
            await run_powershell(f"Start-Process 'https://t.me/{username}'")
            return f"Opened Telegram chat with @{username}."
    return "Please specify what to do with Telegram."


# ============================================================
# GMAIL (opens in browser — full API needs Google OAuth setup)
# ============================================================

@tool(
    name="gmail",
    description="Open Gmail, compose an email, or search emails. Use when user says 'check my email', 'send an email', 'open Gmail'.",
    input_schema={
        "type": "object",
        "properties": {
            "action": {"type": "string", "description": "'open' to open Gmail, 'compose' to start a new email, 'search' to search emails"},
            "to": {"type": "string", "description": "Email address for compose"},
            "subject": {"type": "string", "description": "Email subject for compose"},
            "body": {"type": "string", "description": "Email body for compose"},
            "query": {"type": "string", "description": "Search query for search"},
        },
        "required": ["action"],
    },
)
async def gmail_tool(input_data: dict[str, Any]) -> str:
    action = input_data["action"].lower()
    if action == "open":
        await run_powershell("Start-Process 'https://mail.google.com'")
        return "Opened Gmail."
    elif action == "compose":
        to = input_data.get("to", "")
        subject = input_data.get("subject", "").replace(" ", "%20")
        body = input_data.get("body", "").replace(" ", "%20")
        url = f"https://mail.google.com/mail/?view=cm&to={to}&su={subject}&body={body}"
        await run_powershell(f"Start-Process '{url}'")
        return f"Opened Gmail compose to {to}. Review and click Send."
    elif action == "search":
        query = input_data.get("query", "").replace(" ", "+")
        await run_powershell(f"Start-Process 'https://mail.google.com/mail/#search/{query}'")
        return f"Searching Gmail for: {input_data.get('query', '')}"
    return "Use 'open', 'compose', or 'search'."


# ============================================================
# GOOGLE CALENDAR (opens in browser)
# ============================================================

@tool(
    name="google_calendar",
    description="Open Google Calendar or create an event. Use when user says 'open calendar', 'schedule a meeting', 'what's on my calendar'.",
    input_schema={
        "type": "object",
        "properties": {
            "action": {"type": "string", "description": "'open' to view calendar, 'create' to make an event"},
            "title": {"type": "string", "description": "Event title for create"},
            "date": {"type": "string", "description": "Date in YYYYMMDD format"},
            "time": {"type": "string", "description": "Start time in HHMM format (24hr)"},
        },
        "required": ["action"],
    },
)
async def calendar_tool(input_data: dict[str, Any]) -> str:
    action = input_data["action"].lower()
    if action == "open":
        await run_powershell("Start-Process 'https://calendar.google.com'")
        return "Opened Google Calendar."
    elif action == "create":
        title = input_data.get("title", "New Event").replace(" ", "%20")
        date = input_data.get("date", "")
        time_str = input_data.get("time", "0900")
        if date:
            url = f"https://calendar.google.com/calendar/render?action=TEMPLATE&text={title}&dates={date}T{time_str}00/{date}T{int(time_str[:2])+1:02d}{time_str[2:]}00"
        else:
            url = f"https://calendar.google.com/calendar/render?action=TEMPLATE&text={title}"
        await run_powershell(f"Start-Process '{url}'")
        return f"Opened calendar event creation for '{input_data.get('title', 'New Event')}'. Confirm and save."
    return "Use 'open' or 'create'."


# ============================================================
# NOTION (opens in browser — API needs token in .env)
# ============================================================

@tool(
    name="notion",
    description="Open Notion workspace. Use when user says 'open Notion', 'go to Notion'.",
    input_schema={
        "type": "object",
        "properties": {
            "page": {"type": "string", "description": "Optional: specific page URL or 'home'"},
        },
    },
)
async def notion_tool(input_data: dict[str, Any]) -> str:
    page = input_data.get("page", "home")
    if page == "home" or not page:
        await run_powershell("Start-Process 'https://notion.so'")
        return "Opened Notion."
    else:
        await run_powershell(f"Start-Process '{page}'")
        return f"Opened Notion page."
