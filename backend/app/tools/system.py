"""System tools — PowerShell bridge for Windows automation."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

from app.tools.registry import tool

log = logging.getLogger("jarvis.tools.system")


async def run_powershell(script: str) -> str:
    """Execute a PowerShell script and return output.
    Uses thread pool to avoid Windows asyncio subprocess issues with uvicorn.
    """
    import subprocess

    def _run() -> str:
        try:
            result = subprocess.run(
                ["powershell.exe", "-NoProfile", "-Command", script],
                capture_output=True, text=True, timeout=15,
            )
            if result.returncode != 0:
                err = result.stderr.strip()
                return f"Error: {err}" if err else f"Command failed with code {result.returncode}"
            return result.stdout.strip()
        except subprocess.TimeoutExpired:
            return "Error: Command timed out"

    return await asyncio.to_thread(_run)


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
    description="Open an application on the computer. ALWAYS call this tool when user asks to open ANY app — never assume an app is already open. Use when the user says 'open Chrome', 'launch Notepad', etc.",
    input_schema={
        "type": "object",
        "properties": {
            "app_name": {"type": "string", "description": "Name of the application to open (e.g., 'chrome', 'notepad', 'explorer', 'calculator')"},
        },
        "required": ["app_name"],
    },
)
async def open_app_tool(input_data: dict[str, Any]) -> str:
    import os
    import subprocess as sp

    app = input_data["app_name"].lower().strip()

    # Direct executable paths — bypass PowerShell for reliability
    exe_map = {
        "chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        "google chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        "browser": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        "notepad": "notepad.exe",
        "calculator": "calc.exe",
        "calc": "calc.exe",
        "explorer": "explorer.exe",
        "file explorer": "explorer.exe",
        "files": "explorer.exe",
        "terminal": "wt.exe",
        "cmd": "cmd.exe",
        "powershell": "powershell.exe",
        "spotify": "spotify.exe",
        "vscode": "code",
        "vs code": "code",
        "code": "code",
    }

    # Special protocol launches (settings, etc)
    protocol_map = {
        "settings": "ms-settings:",
    }

    if app in protocol_map:
        os.startfile(protocol_map[app])
        return f"Opened {app}"

    exe = exe_map.get(app, app)

    def _launch():
        try:
            sp.Popen(
                [exe],
                stdout=sp.DEVNULL, stderr=sp.DEVNULL,
                creationflags=sp.DETACHED_PROCESS | sp.CREATE_NEW_PROCESS_GROUP,
            )
            return f"Opened {app}"
        except FileNotFoundError:
            # Try via shell as fallback
            try:
                os.startfile(exe)
                return f"Opened {app}"
            except Exception as e:
                return f"Could not open {app}: {e}"
        except Exception as e:
            return f"Could not open {app}: {e}"

    return await asyncio.to_thread(_launch)


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
    description="Take a screenshot of the current screen and save it. You can specify where to save it — Desktop, Documents, or any folder. Defaults to Desktop if not specified.",
    input_schema={
        "type": "object",
        "properties": {
            "save_path": {
                "type": "string",
                "description": "Where to save. Can be a full path like 'C:\\Users\\suche\\Desktop\\shot.png', or a shortcut like 'desktop', 'documents', 'downloads'. Defaults to Desktop.",
            },
            "filename": {
                "type": "string",
                "description": "Filename for the screenshot (default: jarvis_screenshot_<timestamp>.png)",
            },
        },
    },
)
async def screenshot_tool(input_data: dict[str, Any]) -> str:
    # Resolve save location
    save_path = input_data.get("save_path", "desktop").strip()
    filename = input_data.get("filename", "").strip()

    location_map = {
        "desktop": "C:\\Users\\suche\\Desktop",
        "documents": "C:\\Users\\suche\\Documents",
        "downloads": "C:\\Users\\suche\\Downloads",
        "temp": "$env:TEMP",
    }
    folder = location_map.get(save_path.lower(), "")

    if folder:
        # It's a shortcut name
        if not filename:
            filename = "jarvis_screenshot_$(Get-Date -Format 'yyyyMMdd_HHmmss').png"
        save_target = f"{folder}\\{filename}"
    elif save_path.endswith(".png") or save_path.endswith(".jpg"):
        # Full path provided
        save_target = save_path
    else:
        # Treat as folder path
        if not filename:
            filename = "jarvis_screenshot_$(Get-Date -Format 'yyyyMMdd_HHmmss').png"
        save_target = f"{save_path}\\{filename}"

    script = f"""
    Add-Type -AssemblyName System.Windows.Forms
    Add-Type -AssemblyName System.Drawing
    $screen = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
    $bitmap = New-Object System.Drawing.Bitmap($screen.Width, $screen.Height)
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    $graphics.CopyFromScreen($screen.Location, [System.Drawing.Point]::Empty, $screen.Size)
    $path = "{save_target}"
    $bitmap.Save($path)
    $graphics.Dispose()
    $bitmap.Dispose()
    Write-Output $path
    """
    result = await run_powershell(script)
    return f"Screenshot saved to {result}"


@tool(
    name="lock_pc",
    description="Lock the computer screen.",
    input_schema={"type": "object", "properties": {}},
)
async def lock_pc_tool(input_data: dict[str, Any]) -> str:
    await run_powershell("rundll32.exe user32.dll,LockWorkStation")
    return "Computer locked."


@tool(
    name="set_brightness",
    description="Set screen brightness to a level (0-100).",
    input_schema={
        "type": "object",
        "properties": {
            "level": {"type": "integer", "description": "Brightness 0-100"},
        },
        "required": ["level"],
    },
)
async def set_brightness_tool(input_data: dict[str, Any]) -> str:
    level = max(0, min(100, input_data["level"]))
    script = f"(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1,{level})"
    result = await run_powershell(script)
    return result if result else f"Brightness set to {level}%"


@tool(
    name="toggle_wifi",
    description="Turn WiFi on or off.",
    input_schema={
        "type": "object",
        "properties": {
            "enable": {"type": "boolean", "description": "true to enable, false to disable"},
        },
        "required": ["enable"],
    },
)
async def toggle_wifi_tool(input_data: dict[str, Any]) -> str:
    action = "Enable" if input_data["enable"] else "Disable"
    script = f"Get-NetAdapter -Name 'Wi-Fi' | {action}-NetAdapter -Confirm:$false"
    result = await run_powershell(script)
    return result if result else f"WiFi {'enabled' if input_data['enable'] else 'disabled'}"


@tool(
    name="kill_process",
    description="Close/kill a running application by name. ALWAYS call this tool when user asks to close, kill, or quit ANY app. Never assume an app is already closed. Use when user says 'close Notepad', 'kill Chrome', 'quit Spotify'.",
    input_schema={
        "type": "object",
        "properties": {
            "process_name": {"type": "string", "description": "App name like chrome, spotify, notepad"},
        },
        "required": ["process_name"],
    },
)
async def kill_process_tool(input_data: dict[str, Any]) -> str:
    name = input_data["process_name"].lower().strip()
    process_map = {
        "chrome": "chrome", "google chrome": "chrome",
        "firefox": "firefox", "edge": "msedge",
        "notepad": "Notepad", "spotify": "Spotify",
        "vscode": "Code", "vs code": "Code", "code": "Code",
        "word": "WINWORD", "excel": "EXCEL", "powerpoint": "POWERPNT",
        "teams": "Teams", "discord": "Discord", "slack": "slack",
    }
    proc = process_map.get(name, name)
    # Use Python subprocess directly — PowerShell taskkill has quoting issues
    import subprocess as sp

    def _kill():
        try:
            r = sp.run(["taskkill", "/IM", f"{proc}.exe", "/F"],
                       capture_output=True, text=True, timeout=10)
            if r.returncode == 0:
                return f"Closed {name}"
            # Fallback: try without .exe
            r2 = sp.run(["taskkill", "/IM", proc, "/F"],
                        capture_output=True, text=True, timeout=10)
            if r2.returncode == 0:
                return f"Closed {name}"
            return f"Could not find {name} running"
        except Exception as e:
            return f"Error closing {name}: {e}"

    return await asyncio.to_thread(_kill)


@tool(
    name="minimize_all",
    description="Minimize all windows (show desktop).",
    input_schema={"type": "object", "properties": {}},
)
async def minimize_all_tool(input_data: dict[str, Any]) -> str:
    script = "(New-Object -ComObject Shell.Application).MinimizeAll()"
    await run_powershell(script)
    return "All windows minimized."


@tool(
    name="type_text",
    description="Type text into the currently active window. Use when user says 'type this for me'.",
    input_schema={
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "The text to type"},
        },
        "required": ["text"],
    },
)
async def type_text_tool(input_data: dict[str, Any]) -> str:
    import subprocess as sp
    text = input_data["text"]

    def _type():
        try:
            # Copy text to clipboard using Python
            process = sp.Popen(['clip.exe'], stdin=sp.PIPE)
            process.communicate(text.encode('utf-16-le'))

            # Small delay then send Ctrl+V to paste into active window
            import time
            time.sleep(0.5)

            import ctypes
            user32 = ctypes.windll.user32
            # Key codes: VK_CONTROL=0x11, VK_V=0x56
            # keybd_event sends to OS-level foreground window
            user32.keybd_event(0x11, 0, 0, 0)  # Ctrl down
            user32.keybd_event(0x56, 0, 0, 0)  # V down
            user32.keybd_event(0x56, 0, 2, 0)  # V up
            user32.keybd_event(0x11, 0, 2, 0)  # Ctrl up
            return f"Typed: {text[:50]}"
        except Exception as e:
            return f"Error typing: {e}"

    return await asyncio.to_thread(_type)


@tool(
    name="press_key",
    description="Press a keyboard key or shortcut. Use when user says 'press enter', 'hit tab', 'press escape', 'alt tab', 'ctrl z', 'press backspace'. Works on whatever window is currently focused.",
    input_schema={
        "type": "object",
        "properties": {
            "key": {"type": "string", "description": "Key to press: 'enter', 'tab', 'escape', 'backspace', 'delete', 'up', 'down', 'left', 'right', 'home', 'end', 'space', 'f1'-'f12', 'ctrl+a', 'ctrl+c', 'ctrl+v', 'ctrl+z', 'ctrl+s', 'alt+tab', 'alt+f4', 'ctrl+shift+t'"},
        },
        "required": ["key"],
    },
)
async def press_key_tool(input_data: dict[str, Any]) -> str:
    import ctypes

    key_name = input_data["key"].lower().strip()

    # Virtual key code map
    vk_map = {
        "enter": 0x0D, "return": 0x0D, "tab": 0x09, "escape": 0x1B, "esc": 0x1B,
        "backspace": 0x08, "delete": 0x2E, "space": 0x20,
        "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
        "home": 0x24, "end": 0x23, "pageup": 0x21, "pagedown": 0x22,
        "f1": 0x70, "f2": 0x71, "f3": 0x72, "f4": 0x73, "f5": 0x74,
        "f6": 0x75, "f7": 0x76, "f8": 0x77, "f9": 0x78, "f10": 0x79,
        "f11": 0x7A, "f12": 0x7B,
        "a": 0x41, "b": 0x42, "c": 0x43, "d": 0x44, "e": 0x45,
        "f": 0x46, "g": 0x47, "h": 0x48, "i": 0x49, "j": 0x4A,
        "k": 0x4B, "l": 0x4C, "m": 0x4D, "n": 0x4E, "o": 0x4F,
        "p": 0x50, "q": 0x51, "r": 0x52, "s": 0x53, "t": 0x54,
        "u": 0x55, "v": 0x56, "w": 0x57, "x": 0x58, "y": 0x59, "z": 0x5A,
    }

    # Modifier keys
    VK_CTRL = 0x11
    VK_ALT = 0x12
    VK_SHIFT = 0x10

    def _press():
        user32 = ctypes.windll.user32
        parts = key_name.replace("+", " ").split()
        modifiers = []
        main_key = None

        for p in parts:
            p = p.strip()
            if p in ("ctrl", "control"):
                modifiers.append(VK_CTRL)
            elif p in ("alt",):
                modifiers.append(VK_ALT)
            elif p in ("shift",):
                modifiers.append(VK_SHIFT)
            else:
                main_key = vk_map.get(p)

        if not main_key:
            return f"Unknown key: {key_name}"

        import time
        time.sleep(0.3)

        # Press modifiers down
        for mod in modifiers:
            user32.keybd_event(mod, 0, 0, 0)
        # Press main key
        user32.keybd_event(main_key, 0, 0, 0)
        user32.keybd_event(main_key, 0, 2, 0)  # key up
        # Release modifiers
        for mod in reversed(modifiers):
            user32.keybd_event(mod, 0, 2, 0)

        return f"Pressed {key_name}"

    return await asyncio.to_thread(_press)


@tool(
    name="search_images",
    description="Search for images on Google and open in browser. Use when user says 'show me images of X'.",
    input_schema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "What to search images for"},
        },
        "required": ["query"],
    },
)
async def search_images_tool(input_data: dict[str, Any]) -> str:
    query = input_data["query"].replace(" ", "+").replace("'", "")
    script = f"Start-Process 'https://www.google.com/search?q={query}&tbm=isch'"
    await run_powershell(script)
    return f"Showing images of: {input_data['query']}"


@tool(
    name="search_videos",
    description="Search for videos on YouTube and open in browser. Use when user says 'show me videos of X'.",
    input_schema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "What to search videos for"},
        },
        "required": ["query"],
    },
)
async def search_videos_tool(input_data: dict[str, Any]) -> str:
    query = input_data["query"].replace(" ", "+").replace("'", "")
    script = f"Start-Process 'https://www.youtube.com/results?search_query={query}'"
    await run_powershell(script)
    return f"Showing videos of: {input_data['query']}"


# ============================================================
# WINDOW MANAGEMENT — switch, resize, split, virtual desktops
# ============================================================

@tool(
    name="switch_window",
    description="Switch to a specific open window by app name. Use when user says 'switch to Chrome', 'go to VS Code', 'focus on Spotify'.",
    input_schema={
        "type": "object",
        "properties": {
            "app_name": {"type": "string", "description": "Name of the app window to switch to (chrome, vscode, spotify, notepad, etc.)"},
        },
        "required": ["app_name"],
    },
)
async def switch_window_tool(input_data: dict[str, Any]) -> str:
    app = input_data["app_name"].lower().strip()
    name_map = {
        "chrome": "chrome", "google chrome": "chrome", "browser": "chrome",
        "vscode": "Code", "vs code": "Code", "code": "Code",
        "notepad": "Notepad", "spotify": "Spotify", "discord": "Discord",
        "slack": "slack", "terminal": "WindowsTerminal", "explorer": "explorer",
        "word": "WINWORD", "excel": "EXCEL", "teams": "Teams",
        "edge": "msedge", "firefox": "firefox",
    }
    proc = name_map.get(app, app)
    # Retry up to 3 times with delay — handles freshly opened apps
    script = f"""
    Add-Type @"
    using System; using System.Runtime.InteropServices;
    public class WinSwitch {{
        [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
        [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
    }}
"@
    $found = $false
    for ($i = 0; $i -lt 4; $i++) {{
        $p = Get-Process -Name '{proc}' -ErrorAction SilentlyContinue | Where-Object {{ $_.MainWindowHandle -ne 0 }} | Select-Object -First 1
        if ($p) {{
            [WinSwitch]::ShowWindow($p.MainWindowHandle, 9)
            [WinSwitch]::SetForegroundWindow($p.MainWindowHandle)
            $found = $true
            Write-Output "Switched to {app}"
            break
        }}
        Start-Sleep -Milliseconds 800
    }}
    if (-not $found) {{
        Write-Output "Could not find {app} window"
    }}
    """
    return await run_powershell(script)


@tool(
    name="snap_window",
    description="Snap a window to left half, right half, or maximize. Specify which app to snap. Use when user says 'snap Chrome left', 'snap JARVIS right', 'maximize Chrome'.",
    input_schema={
        "type": "object",
        "properties": {
            "position": {"type": "string", "description": "'left', 'right', 'maximize', or 'restore'"},
            "app_name": {"type": "string", "description": "Which app window to snap (chrome, jarvis, notepad, etc.). Required."},
        },
        "required": ["position", "app_name"],
    },
)
async def snap_window_tool(input_data: dict[str, Any]) -> str:
    pos = input_data["position"].lower().strip()
    app = input_data.get("app_name", "").lower().strip()

    # Build PowerShell window finder based on app name
    # KEY: JARVIS runs in Chrome. "chrome"/"browser" = Chrome WITHOUT JARVIS title.
    proc_map = {
        "notepad": "Notepad", "vscode": "Code", "vs code": "Code",
        "explorer": "explorer", "discord": "Discord", "spotify": "Spotify",
        "edge": "msedge",
    }

    if app == "jarvis":
        finder = "Get-Process -Name 'chrome' -EA SilentlyContinue | Where-Object { $_.MainWindowHandle -ne 0 -and $_.MainWindowTitle -like '*JARVIS*' } | Select-Object -First 1"
    elif app in ("chrome", "google chrome", "browser"):
        finder = "Get-Process -Name 'chrome' -EA SilentlyContinue | Where-Object { $_.MainWindowHandle -ne 0 -and $_.MainWindowTitle -notlike '*JARVIS*' } | Select-Object -First 1"
    else:
        proc = proc_map.get(app, app)
        finder = f"Get-Process -Name '{proc}' -EA SilentlyContinue | Where-Object {{ $_.MainWindowHandle -ne 0 }} | Select-Object -First 1"

    script = f"""
    Add-Type -AssemblyName System.Windows.Forms
    Add-Type @"
    using System; using System.Runtime.InteropServices;
    public class WinSnap {{
        [DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr hWnd, IntPtr hWndInsertAfter, int X, int Y, int cx, int cy, uint uFlags);
        [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
    }}
"@
    $screen = [System.Windows.Forms.Screen]::PrimaryScreen.WorkingArea
    $p = {finder}
    if ($p) {{
        $hwnd = $p.MainWindowHandle
        $null = [WinSnap]::ShowWindow($hwnd, 9)
        Start-Sleep -Milliseconds 300
        $w = $screen.Width
        $h = $screen.Height
        $x = $screen.X
        $y = $screen.Y
        switch ('{pos}') {{
            'left'     {{ $null = [WinSnap]::SetWindowPos($hwnd, [IntPtr]::Zero, $x, $y, $w/2, $h, 0x0034) }}
            'right'    {{ $null = [WinSnap]::SetWindowPos($hwnd, [IntPtr]::Zero, $x + $w/2, $y, $w/2, $h, 0x0034) }}
            'maximize' {{ $null = [WinSnap]::ShowWindow($hwnd, 3) }}
            'restore'  {{ $null = [WinSnap]::ShowWindow($hwnd, 9) }}
        }}
        Start-Sleep -Milliseconds 200
        Write-Output "Snapped {app} to {pos}"
    }} else {{
        Write-Output "Could not find {app} window"
    }}
    """
    return await run_powershell(script)


@tool(
    name="split_screen",
    description="Split screen between two apps — puts first app left, second app right. Use when user says 'split Chrome and VS Code'.",
    input_schema={
        "type": "object",
        "properties": {
            "left_app": {"type": "string", "description": "App for the left half"},
            "right_app": {"type": "string", "description": "App for the right half"},
        },
        "required": ["left_app", "right_app"],
    },
)
async def split_screen_tool(input_data: dict[str, Any]) -> str:
    left = input_data["left_app"]
    right = input_data["right_app"]
    await snap_window_tool({"position": "left", "app_name": left})
    await asyncio.sleep(0.5)
    await snap_window_tool({"position": "right", "app_name": right})
    return f"Split screen: {left} (left) | {right} (right)"


@tool(
    name="virtual_desktop",
    description="Manage virtual desktops. Create new, switch between them, or close current. Use when user says 'new desktop', 'switch desktop'.",
    input_schema={
        "type": "object",
        "properties": {
            "action": {"type": "string", "description": "'new' to create, 'next' to go right, 'prev' to go left, 'close' to close current desktop"},
        },
        "required": ["action"],
    },
)
async def virtual_desktop_tool(input_data: dict[str, Any]) -> str:
    action = input_data["action"].lower().strip()
    commands = {
        "new": "^#d",       # Ctrl+Win+D
        "next": "^#{RIGHT}",  # Ctrl+Win+Right
        "prev": "^#{LEFT}",   # Ctrl+Win+Left
        "close": "^#{F4}",    # Ctrl+Win+F4
    }
    keys = commands.get(action, commands.get("new"))
    script = f"""
    Add-Type -AssemblyName System.Windows.Forms
    [System.Windows.Forms.SendKeys]::SendWait('{keys}')
    Write-Output "Virtual desktop: {action}"
    """
    return await run_powershell(script)


@tool(
    name="task_manager_info",
    description="Get top processes by CPU or memory usage. Use when user says 'what's using CPU', 'what's eating my RAM'.",
    input_schema={
        "type": "object",
        "properties": {
            "sort_by": {"type": "string", "description": "'cpu' or 'memory' (default: cpu)"},
        },
    },
)
async def task_manager_tool(input_data: dict[str, Any]) -> str:
    sort = input_data.get("sort_by", "cpu").lower()
    if sort == "memory":
        script = """
        Get-Process | Sort-Object WorkingSet64 -Descending | Select-Object -First 8 |
        ForEach-Object { "$($_.ProcessName): $([math]::Round($_.WorkingSet64/1MB, 0)) MB" }
        """
    else:
        script = """
        Get-Process | Sort-Object CPU -Descending | Select-Object -First 8 |
        ForEach-Object { "$($_.ProcessName): $([math]::Round($_.CPU, 1)) sec CPU time" }
        """
    return await run_powershell(script)


# ============================================================
# SYSTEM CONTROL — shutdown, bluetooth, night light, etc.
# ============================================================

@tool(
    name="shutdown_timer",
    description="Schedule shutdown, restart, or sleep after a delay. Use when user says 'shutdown in 30 minutes', 'restart in 1 hour', 'sleep timer'.",
    input_schema={
        "type": "object",
        "properties": {
            "action": {"type": "string", "description": "'shutdown', 'restart', 'sleep', or 'cancel' to cancel a pending timer"},
            "minutes": {"type": "integer", "description": "Minutes until action (ignored for cancel)"},
        },
        "required": ["action"],
    },
)
async def shutdown_timer_tool(input_data: dict[str, Any]) -> str:
    action = input_data["action"].lower().strip()
    minutes = input_data.get("minutes", 0)
    seconds = minutes * 60

    if action == "cancel":
        await run_powershell("shutdown /a")
        return "Shutdown timer cancelled."
    elif action == "shutdown":
        await run_powershell(f"shutdown /s /t {seconds}")
        return f"Shutting down in {minutes} minutes."
    elif action == "restart":
        await run_powershell(f"shutdown /r /t {seconds}")
        return f"Restarting in {minutes} minutes."
    elif action == "sleep":
        if minutes > 0:
            script = f"Start-Sleep -Seconds {seconds}; rundll32.exe powrprof.dll,SetSuspendState 0,1,0"
            await run_powershell(script)
            return f"Going to sleep in {minutes} minutes."
        else:
            await run_powershell("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")
            return "Going to sleep now."
    return f"Unknown action: {action}"


@tool(
    name="toggle_bluetooth",
    description="Turn Bluetooth on or off. ALWAYS call this tool when user asks to enable/disable Bluetooth. Never assume current state.",
    input_schema={
        "type": "object",
        "properties": {
            "enable": {"type": "boolean", "description": "true to enable, false to disable"},
        },
        "required": ["enable"],
    },
)
async def toggle_bluetooth_tool(input_data: dict[str, Any]) -> str:
    enable = input_data["enable"]
    # Use Windows Radio Management API via PowerShell
    action_word = "enable" if enable else "disable"
    script = f"""
    Add-Type -AssemblyName System.Runtime.WindowsRuntime
    $asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {{ $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' }})[0]
    Function Await($WinRtTask, $ResultType) {{
        $asTask = $asTaskGeneric.MakeGenericMethod($ResultType)
        $netTask = $asTask.Invoke($null, @($WinRtTask))
        $netTask.Wait(-1) | Out-Null
        $netTask.Result
    }}
    try {{
        [Windows.Devices.Radios.Radio,Windows.System.Devices,ContentType=WindowsRuntime] | Out-Null
        $radios = Await ([Windows.Devices.Radios.Radio]::GetRadiosAsync()) ([System.Collections.Generic.IReadOnlyList[Windows.Devices.Radios.Radio]])
        $bt = $radios | Where-Object {{ $_.Kind -eq 'Bluetooth' }}
        if ($bt) {{
            $state = if ('{action_word}' -eq 'enable') {{ 'On' }} else {{ 'Off' }}
            Await ($bt.SetStateAsync($state)) ([Windows.Devices.Radios.RadioAccessStatus]) | Out-Null
            Write-Output "Bluetooth {action_word}d"
        }} else {{
            Write-Output "No Bluetooth radio found"
        }}
    }} catch {{
        # Fallback: open Bluetooth settings
        Start-Process 'ms-settings:bluetooth'
        Write-Output "Opened Bluetooth settings - please toggle manually"
    }}
    """
    return await run_powershell(script)


@tool(
    name="toggle_night_light",
    description="Turn Windows Night Light (blue light filter) on or off. Use when user says 'night light', 'night mode', 'blue light'.",
    input_schema={
        "type": "object",
        "properties": {
            "enable": {"type": "boolean", "description": "true to enable, false to disable"},
        },
        "required": ["enable"],
    },
)
async def toggle_night_light_tool(input_data: dict[str, Any]) -> str:
    enable = input_data["enable"]
    # Open Night Light settings
    script = "Start-Process 'ms-settings:nightlight'"
    await run_powershell(script)
    return f"Opened Night Light settings — please toggle {'on' if enable else 'off'}"


@tool(
    name="change_wallpaper",
    description="Change the desktop wallpaper. Provide a file path to an image. Use when user says 'change wallpaper', 'set background'.",
    input_schema={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Full path to the image file (jpg, png, bmp)"},
        },
        "required": ["path"],
    },
)
async def change_wallpaper_tool(input_data: dict[str, Any]) -> str:
    path = input_data["path"].replace("'", "''")
    script = f"""
    Add-Type -TypeDefinition @"
    using System; using System.Runtime.InteropServices;
    public class Wallpaper {{
        [DllImport("user32.dll", CharSet = CharSet.Auto)]
        public static extern int SystemParametersInfo(int uAction, int uParam, string lpvParam, int fuWinIni);
    }}
"@
    [Wallpaper]::SystemParametersInfo(0x0014, 0, '{path}', 0x0003)
    Write-Output "Wallpaper changed"
    """
    result = await run_powershell(script)
    return result if "changed" in result else f"Failed: {result}"


@tool(
    name="internet_speed",
    description="Check internet download and upload speed. Use when user says 'check internet speed', 'how fast is my WiFi'.",
    input_schema={"type": "object", "properties": {}},
)
async def internet_speed_tool(input_data: dict[str, Any]) -> str:
    # Quick speed estimate using PowerShell download test
    script = """
    $url = 'http://speedtest.tele2.net/1MB.zip'
    $start = Get-Date
    try {
        $null = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 15
        $elapsed = ((Get-Date) - $start).TotalSeconds
        $speedMbps = [math]::Round(8 / $elapsed, 1)
        Write-Output "Download speed: approximately $speedMbps Mbps (tested with 1MB file)"
    } catch {
        Write-Output "Speed test failed — check your internet connection"
    }
    """
    return await run_powershell(script)


@tool(
    name="toggle_battery_saver",
    description="Turn battery saver mode on or off. Use when user says 'battery saver', 'power saving'.",
    input_schema={
        "type": "object",
        "properties": {
            "enable": {"type": "boolean", "description": "true to enable, false to disable"},
        },
        "required": ["enable"],
    },
)
async def toggle_battery_saver_tool(input_data: dict[str, Any]) -> str:
    enable = input_data["enable"]
    if enable:
        script = "powercfg /setactive SCHEME_MAX"
        await run_powershell(script)
        return "Switched to power saver mode."
    else:
        script = "powercfg /setactive SCHEME_BALANCED"
        await run_powershell(script)
        return "Switched to balanced power mode."


@tool(
    name="startup_apps",
    description="List or manage startup apps. Use when user says 'what starts on boot', 'disable Discord startup'.",
    input_schema={
        "type": "object",
        "properties": {
            "action": {"type": "string", "description": "'list' to see startup apps, 'disable' to disable one, 'enable' to enable one"},
            "app_name": {"type": "string", "description": "App name (only needed for enable/disable)"},
        },
        "required": ["action"],
    },
)
async def startup_apps_tool(input_data: dict[str, Any]) -> str:
    action = input_data["action"].lower()
    if action == "list":
        script = """
        $reg = Get-ItemProperty 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Run' -ErrorAction SilentlyContinue
        if ($reg) {
            $reg.PSObject.Properties | Where-Object { $_.Name -notin @('PSPath','PSParentPath','PSChildName','PSDrive','PSProvider') } |
            ForEach-Object { "$($_.Name)" }
        } else { Write-Output "No startup apps found" }
        """
        return await run_powershell(script)
    elif action in ("disable", "enable"):
        app = input_data.get("app_name", "")
        if not app:
            return "Please specify which app to modify."
        if action == "disable":
            script = f"Remove-ItemProperty 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Run' -Name '{app}' -ErrorAction SilentlyContinue; Write-Output 'Disabled {app} from startup'"
        else:
            return f"To enable {app} at startup, you'll need to add it through the app's settings."
        return await run_powershell(script)
    return "Use 'list', 'enable', or 'disable'"
