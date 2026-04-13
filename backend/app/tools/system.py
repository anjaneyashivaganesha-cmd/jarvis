"""System tools — PowerShell bridge for Windows automation."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any

from app.tools.registry import tool

log = logging.getLogger("jarvis.tools.system")


async def run_powershell(script: str) -> str:
    """Execute a PowerShell script and return output."""
    proc = await asyncio.create_subprocess_exec(
        "powershell.exe", "-NoProfile", "-Command", script,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=10)
    output = stdout.decode("utf-8", errors="replace").strip()
    if proc.returncode != 0:
        err = stderr.decode("utf-8", errors="replace").strip()
        return f"Error: {err}" if err else f"Command failed with code {proc.returncode}"
    return output


@tool(
    name="get_time",
    description="Get the current date and time.",
    input_schema={"type": "object", "properties": {}},
)
async def get_time_tool(input_data: dict[str, Any]) -> str:
    now = datetime.now()
    return now.strftime("It's %A, %B %d, %Y at %I:%M %p")


@tool(
    name="open_app",
    description="Open an application on the computer. Use when the user says 'open Chrome', 'launch Notepad', etc.",
    input_schema={
        "type": "object",
        "properties": {
            "app_name": {"type": "string", "description": "Name of the application to open (e.g., 'chrome', 'notepad', 'explorer', 'calculator')"},
        },
        "required": ["app_name"],
    },
)
async def open_app_tool(input_data: dict[str, Any]) -> str:
    app = input_data["app_name"].lower().strip()

    app_map = {
        "chrome": "Start-Process chrome",
        "google chrome": "Start-Process chrome",
        "browser": "Start-Process chrome",
        "notepad": "Start-Process notepad",
        "calculator": "Start-Process calc",
        "calc": "Start-Process calc",
        "explorer": "Start-Process explorer",
        "file explorer": "Start-Process explorer",
        "files": "Start-Process explorer",
        "terminal": "Start-Process wt",
        "cmd": "Start-Process cmd",
        "powershell": "Start-Process powershell",
        "settings": "Start-Process ms-settings:",
        "spotify": "Start-Process spotify",
        "vscode": "Start-Process code",
        "vs code": "Start-Process code",
        "code": "Start-Process code",
    }

    cmd = app_map.get(app)
    if not cmd:
        cmd = f"Start-Process '{app}'"

    result = await run_powershell(cmd)
    return result if result else f"Opened {app}"


@tool(
    name="system_info",
    description="Get system information like battery, CPU, memory usage.",
    input_schema={"type": "object", "properties": {}},
)
async def system_info_tool(input_data: dict[str, Any]) -> str:
    script = """
    $cpu = (Get-CimInstance Win32_Processor).LoadPercentage
    $mem = Get-CimInstance Win32_OperatingSystem
    $totalMem = [math]::Round($mem.TotalVisibleMemorySize / 1MB, 1)
    $freeMem = [math]::Round($mem.FreePhysicalMemory / 1MB, 1)
    $usedMem = $totalMem - $freeMem
    $battery = Get-CimInstance Win32_Battery -ErrorAction SilentlyContinue
    $battPct = if ($battery) { "$($battery.EstimatedChargeRemaining)%" } else { "No battery" }
    Write-Output "CPU: $cpu% | RAM: $usedMem/$totalMem GB used | Battery: $battPct"
    """
    return await run_powershell(script)


@tool(
    name="set_volume",
    description="Set the system volume to a specific level (0-100).",
    input_schema={
        "type": "object",
        "properties": {
            "level": {"type": "integer", "description": "Volume level from 0 to 100"},
        },
        "required": ["level"],
    },
)
async def set_volume_tool(input_data: dict[str, Any]) -> str:
    level = max(0, min(100, input_data["level"]))
    # Use nircmd-style approach via PowerShell
    script = f"""
    $wshell = New-Object -ComObject WScript.Shell
    # Mute first, then set
    1..50 | ForEach-Object {{ $wshell.SendKeys([char]174) }}
    $steps = [math]::Round({level} / 2)
    1..$steps | ForEach-Object {{ $wshell.SendKeys([char]175) }}
    Write-Output "Volume set to approximately {level}%"
    """
    return await run_powershell(script)


@tool(
    name="web_search",
    description="Open a web search in the default browser. Use when the user asks to search for something.",
    input_schema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "The search query"},
        },
        "required": ["query"],
    },
)
async def web_search_tool(input_data: dict[str, Any]) -> str:
    query = input_data["query"].replace("'", "''")
    encoded = query.replace(" ", "+")
    script = f"Start-Process 'https://www.google.com/search?q={encoded}'"
    await run_powershell(script)
    return f"Searching the web for: {query}"


@tool(
    name="screenshot",
    description="Take a screenshot of the current screen.",
    input_schema={"type": "object", "properties": {}},
)
async def screenshot_tool(input_data: dict[str, Any]) -> str:
    script = """
    Add-Type -AssemblyName System.Windows.Forms
    $screen = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
    $bitmap = New-Object System.Drawing.Bitmap($screen.Width, $screen.Height)
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    $graphics.CopyFromScreen($screen.Location, [System.Drawing.Point]::Empty, $screen.Size)
    $path = "$env:TEMP\\jarvis_screenshot.png"
    $bitmap.Save($path)
    $graphics.Dispose()
    $bitmap.Dispose()
    Write-Output $path
    """
    result = await run_powershell(script)
    return f"Screenshot saved to {result}"
