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


@tool(
    name="move_file",
    description="Move or rename a file. Use when user says 'move X to desktop', 'rename file', 'put that file in Documents'.",
    input_schema={
        "type": "object",
        "properties": {
            "source": {"type": "string", "description": "Full path of the file to move"},
            "destination": {"type": "string", "description": "Destination path or folder. Can use shortcuts: 'desktop', 'documents', 'downloads'"},
        },
        "required": ["source", "destination"],
    },
)
async def move_file_tool(input_data: dict[str, Any]) -> str:
    source = input_data["source"].replace("'", "''")
    dest = input_data["destination"].strip()

    folder_map = {
        "desktop": "C:\\Users\\suche\\Desktop",
        "documents": "C:\\Users\\suche\\Documents",
        "downloads": "C:\\Users\\suche\\Downloads",
    }
    resolved = folder_map.get(dest.lower(), dest)
    resolved = resolved.replace("'", "''")

    script = f"Move-Item -Path '{source}' -Destination '{resolved}' -Force; Write-Output 'Moved'"
    result = await run_powershell(script)
    return f"Moved to {resolved}" if "Moved" in result else result


@tool(
    name="copy_file",
    description="Copy a file to another location. Use when user says 'copy this to desktop', 'make a backup of X'.",
    input_schema={
        "type": "object",
        "properties": {
            "source": {"type": "string", "description": "Full path of the file to copy"},
            "destination": {"type": "string", "description": "Destination path or folder. Can use shortcuts: 'desktop', 'documents', 'downloads'"},
        },
        "required": ["source", "destination"],
    },
)
async def copy_file_tool(input_data: dict[str, Any]) -> str:
    source = input_data["source"].replace("'", "''")
    dest = input_data["destination"].strip()

    folder_map = {
        "desktop": "C:\\Users\\suche\\Desktop",
        "documents": "C:\\Users\\suche\\Documents",
        "downloads": "C:\\Users\\suche\\Downloads",
    }
    resolved = folder_map.get(dest.lower(), dest)
    resolved = resolved.replace("'", "''")

    script = f"Copy-Item -Path '{source}' -Destination '{resolved}' -Force; Write-Output 'Copied'"
    result = await run_powershell(script)
    return f"Copied to {resolved}" if "Copied" in result else result


@tool(
    name="create_folder",
    description="Create a new folder. Use when user says 'make a folder called X', 'create directory'.",
    input_schema={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Full path for the new folder, or just a name to create on Desktop"},
        },
        "required": ["path"],
    },
)
async def create_folder_tool(input_data: dict[str, Any]) -> str:
    path = input_data["path"].replace("'", "''")
    # If just a name with no path separator, create on Desktop
    if "\\" not in path and "/" not in path:
        path = f"C:\\Users\\suche\\Desktop\\{path}"
    script = f"New-Item -Path '{path}' -ItemType Directory -Force | Select-Object -ExpandProperty FullName"
    result = await run_powershell(script)
    return f"Created folder: {result}" if result else "Failed to create folder"


@tool(
    name="delete_file",
    description="Delete a file (moves to recycle bin, not permanent). Use when user says 'delete X', 'remove that file'.",
    input_schema={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Full path of the file to delete"},
        },
        "required": ["path"],
    },
)
async def delete_file_tool(input_data: dict[str, Any]) -> str:
    path = input_data["path"].replace("'", "''")
    # Move to recycle bin instead of permanent delete
    script = f"""
    $shell = New-Object -ComObject Shell.Application
    $item = $shell.NameSpace(0).ParseName('{path}')
    if ($item) {{
        $item.InvokeVerb('delete')
        Write-Output 'Moved to recycle bin'
    }} else {{
        Write-Output 'File not found'
    }}
    """
    result = await run_powershell(script)
    return result
