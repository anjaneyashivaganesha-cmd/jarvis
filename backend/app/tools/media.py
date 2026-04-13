"""Media tools — music control, YouTube, screen recording."""

from __future__ import annotations

import logging
from typing import Any

from app.tools.registry import tool
from app.tools.system import run_powershell

log = logging.getLogger("jarvis.tools.media")


@tool(
    name="media_play_pause",
    description="Play or pause the current media (music/video). Use when user says 'play', 'pause', 'resume'.",
    input_schema={"type": "object", "properties": {}},
)
async def media_play_pause_tool(input_data: dict[str, Any]) -> str:
    script = """
    $wshell = New-Object -ComObject WScript.Shell
    $wshell.SendKeys([char]0xB3)
    Write-Output "Toggled play/pause"
    """
    return await run_powershell(script)


@tool(
    name="media_next",
    description="Skip to next track. Use when user says 'next song', 'skip'.",
    input_schema={"type": "object", "properties": {}},
)
async def media_next_tool(input_data: dict[str, Any]) -> str:
    script = """
    $wshell = New-Object -ComObject WScript.Shell
    $wshell.SendKeys([char]0xB0)
    Write-Output "Skipped to next track"
    """
    return await run_powershell(script)


@tool(
    name="media_previous",
    description="Go to previous track. Use when user says 'previous song', 'go back'.",
    input_schema={"type": "object", "properties": {}},
)
async def media_previous_tool(input_data: dict[str, Any]) -> str:
    script = """
    $wshell = New-Object -ComObject WScript.Shell
    $wshell.SendKeys([char]0xB1)
    Write-Output "Previous track"
    """
    return await run_powershell(script)


@tool(
    name="open_youtube",
    description="Search and open YouTube for a query. Use when user says 'play X on YouTube'.",
    input_schema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "What to search on YouTube"},
        },
        "required": ["query"],
    },
)
async def open_youtube_tool(input_data: dict[str, Any]) -> str:
    query = input_data["query"].replace(" ", "+").replace("'", "")
    script = f"Start-Process 'https://www.youtube.com/results?search_query={query}'"
    await run_powershell(script)
    return f"Searching YouTube for: {input_data['query']}"


@tool(
    name="screen_record",
    description="Start or stop screen recording using built-in Windows Game Bar.",
    input_schema={
        "type": "object",
        "properties": {
            "action": {"type": "string", "description": "'start' or 'stop'"},
        },
        "required": ["action"],
    },
)
async def screen_record_tool(input_data: dict[str, Any]) -> str:
    action = input_data["action"].lower()
    if action == "start":
        script = """
        $wshell = New-Object -ComObject WScript.Shell
        $wshell.SendKeys('^%r')
        Write-Output "Screen recording started (Win+Alt+R)"
        """
    else:
        script = """
        $wshell = New-Object -ComObject WScript.Shell
        $wshell.SendKeys('^%r')
        Write-Output "Screen recording stopped"
        """
    return await run_powershell(script)


@tool(
    name="mute_unmute",
    description="Mute or unmute system audio.",
    input_schema={"type": "object", "properties": {}},
)
async def mute_unmute_tool(input_data: dict[str, Any]) -> str:
    script = """
    $wshell = New-Object -ComObject WScript.Shell
    $wshell.SendKeys([char]0xAD)
    Write-Output "Toggled mute"
    """
    return await run_powershell(script)
