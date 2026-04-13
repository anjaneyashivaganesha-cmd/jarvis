"""File tools — file search, window management."""

from __future__ import annotations

import logging
from typing import Any

from app.tools.registry import tool
from app.tools.system import run_powershell

log = logging.getLogger("jarvis.tools.files")


@tool(
    name="find_file",
    description="Search for a file on the computer by name. Use when user says 'find my resume', 'where is X file'.",
    input_schema={
        "type": "object",
        "properties": {
            "filename": {"type": "string", "description": "File name or partial name to search for"},
            "location": {"type": "string", "description": "Where to search: Desktop, Documents, Downloads, or everywhere", "default": "common"},
        },
        "required": ["filename"],
    },
)
async def find_file_tool(input_data: dict[str, Any]) -> str:
    name = input_data["filename"].replace("'", "''")
    location = input_data.get("location", "common").lower()

    if location == "everywhere":
        paths = "C:\\Users\\suche"
    else:
        paths = "C:\\Users\\suche\\Desktop', 'C:\\Users\\suche\\Documents', 'C:\\Users\\suche\\Downloads"

    script = f"""
    $results = @('{paths}') | ForEach-Object {{
        Get-ChildItem -Path $_ -Recurse -Filter '*{name}*' -ErrorAction SilentlyContinue | Select-Object -First 10
    }}
    if ($results) {{
        $results | ForEach-Object {{ $_.FullName }}
    }} else {{
        Write-Output "No files found matching '{name}'"
    }}
    """
    result = await run_powershell(script)
    return result[:500]


@tool(
    name="open_file",
    description="Open a file by its full path.",
    input_schema={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Full file path"},
        },
        "required": ["path"],
    },
)
async def open_file_tool(input_data: dict[str, Any]) -> str:
    path = input_data["path"].replace("'", "''")
    script = f"Start-Process '{path}'"
    result = await run_powershell(script)
    return result if result else f"Opened: {path}"


@tool(
    name="list_running_apps",
    description="List all currently running applications.",
    input_schema={"type": "object", "properties": {}},
)
async def list_running_apps_tool(input_data: dict[str, Any]) -> str:
    script = """
    Get-Process | Where-Object { $_.MainWindowTitle -ne '' } |
    Select-Object -Property ProcessName, MainWindowTitle -Unique |
    Format-Table -AutoSize | Out-String
    """
    result = await run_powershell(script)
    return result[:500] if result else "No visible apps running."


@tool(
    name="disk_space",
    description="Check available disk space.",
    input_schema={"type": "object", "properties": {}},
)
async def disk_space_tool(input_data: dict[str, Any]) -> str:
    script = """
    Get-PSDrive -PSProvider FileSystem | Where-Object { $_.Used -gt 0 } |
    ForEach-Object {
        $used = [math]::Round($_.Used / 1GB, 1)
        $free = [math]::Round($_.Free / 1GB, 1)
        $total = $used + $free
        Write-Output "$($_.Name): drive - $free GB free / $total GB total"
    }
    """
    return await run_powershell(script)


@tool(
    name="empty_recycle_bin",
    description="Show recycle bin size. Does NOT delete — just shows info.",
    input_schema={"type": "object", "properties": {}},
)
async def recycle_bin_tool(input_data: dict[str, Any]) -> str:
    script = """
    $shell = New-Object -ComObject Shell.Application
    $rb = $shell.NameSpace(0x0a)
    $count = $rb.Items().Count
    Write-Output "Recycle bin has $count items."
    """
    return await run_powershell(script)
