"""Screen control tools — AI vision + mouse/keyboard automation."""

from __future__ import annotations

import asyncio
import logging
import os
import tempfile
from typing import Any

from app.tools.registry import tool
from app.tools.system import run_powershell
from app.llm import vision_analyze, vision_find_element

log = logging.getLogger("jarvis.tools.vision")


async def _take_screenshot_temp() -> str:
    """Take a screenshot and return the temp file path."""
    path = os.path.join(tempfile.gettempdir(), "jarvis_vision.png")
    script = f"""
    Add-Type -AssemblyName System.Windows.Forms
    Add-Type -AssemblyName System.Drawing
    $screen = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
    $bitmap = New-Object System.Drawing.Bitmap($screen.Width, $screen.Height)
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    $graphics.CopyFromScreen($screen.Location, [System.Drawing.Point]::Empty, $screen.Size)
    $bitmap.Save('{path}')
    $graphics.Dispose()
    $bitmap.Dispose()
    Write-Output '{path}'
    """
    await run_powershell(script)
    return path


async def _click_at(x: int, y: int) -> str:
    """Click at specific screen coordinates."""
    script = f"""
    Add-Type -AssemblyName System.Windows.Forms
    Add-Type @"
    using System; using System.Runtime.InteropServices;
    public class MouseClick {{
        [DllImport("user32.dll")] public static extern bool SetCursorPos(int X, int Y);
        [DllImport("user32.dll")] public static extern void mouse_event(int dwFlags, int dx, int dy, int dwData, int dwExtraInfo);
    }}
"@
    [MouseClick]::SetCursorPos({x}, {y})
    Start-Sleep -Milliseconds 100
    [MouseClick]::mouse_event(0x02, 0, 0, 0, 0)
    [MouseClick]::mouse_event(0x04, 0, 0, 0, 0)
    Write-Output "Clicked at ({x}, {y})"
    """
    return await run_powershell(script)


@tool(
    name="see_screen",
    description="See what's on the screen using AI vision. Takes a screenshot and describes it. Use when user says 'what's on my screen', 'read this', 'what do you see'.",
    input_schema={
        "type": "object",
        "properties": {
            "question": {"type": "string", "description": "What to look for or describe about the screen (default: general description)"},
        },
    },
)
async def see_screen_tool(input_data: dict[str, Any]) -> str:
    question = input_data.get("question", "What's on this screen? Give me the key information — any text, numbers, names, or important details visible.")
    path = await _take_screenshot_temp()
    result = await vision_analyze(path, question)
    return result


@tool(
    name="click_element",
    description="Click a button, link, or UI element on screen by describing it. Uses AI vision to find and click. Use when user says 'click the X button', 'click submit', 'press the red button'.",
    input_schema={
        "type": "object",
        "properties": {
            "element": {"type": "string", "description": "Description of what to click (e.g., 'the submit button', 'the Chrome icon', 'the close button')"},
        },
        "required": ["element"],
    },
)
async def click_element_tool(input_data: dict[str, Any]) -> str:
    element = input_data["element"]
    path = await _take_screenshot_temp()
    result = await vision_find_element(path, element)

    if result.get("found"):
        x, y = result["x"], result["y"]
        click_result = await _click_at(x, y)
        return f"Found '{element}' at ({x}, {y}) and clicked it. {result.get('description', '')}"
    else:
        return f"Could not find '{element}' on screen. {result.get('description', '')}"


@tool(
    name="read_screen_text",
    description="Read and extract text visible on the screen. Use when user says 'read that', 'what does it say', 'read the error message'.",
    input_schema={
        "type": "object",
        "properties": {
            "area": {"type": "string", "description": "Which part to read: 'all', 'center', 'top', 'bottom', or describe a specific area (default: all visible text)"},
        },
    },
)
async def read_screen_text_tool(input_data: dict[str, Any]) -> str:
    area = input_data.get("area", "all")
    path = await _take_screenshot_temp()
    prompt = f"Read the important text on this screen. Focus on: {area}. Give me the actual content — names, numbers, dates, messages. Skip UI labels and navigation. Just the real content the user cares about."
    return await vision_analyze(path, prompt)


@tool(
    name="fill_form_field",
    description="Fill a form field by describing it. Finds the field with AI vision, clicks it, and types the value. Use when user says 'fill in the email', 'type my name in the field'.",
    input_schema={
        "type": "object",
        "properties": {
            "field": {"type": "string", "description": "Description of the form field (e.g., 'email input', 'search box', 'name field')"},
            "value": {"type": "string", "description": "The text to type into the field"},
        },
        "required": ["field", "value"],
    },
)
async def fill_form_tool(input_data: dict[str, Any]) -> str:
    field = input_data["field"]
    value = input_data["value"]

    path = await _take_screenshot_temp()
    result = await vision_find_element(path, field)

    if result.get("found"):
        x, y = result["x"], result["y"]
        # Click the field
        await _click_at(x, y)
        await asyncio.sleep(0.3)
        # Clear existing content and type new value
        safe_value = value.replace("'", "''")
        script = f"""
        Add-Type -AssemblyName System.Windows.Forms
        [System.Windows.Forms.SendKeys]::SendWait('^a')
        Start-Sleep -Milliseconds 100
        [System.Windows.Forms.SendKeys]::SendWait('{safe_value}')
        Write-Output "Typed"
        """
        await run_powershell(script)
        return f"Found '{field}' and typed '{value}' into it."
    else:
        return f"Could not find the field '{field}' on screen."


@tool(
    name="scroll_screen",
    description="Scroll the screen up or down. Use when user says 'scroll down', 'scroll up', 'page down'.",
    input_schema={
        "type": "object",
        "properties": {
            "direction": {"type": "string", "description": "'up' or 'down'"},
            "amount": {"type": "integer", "description": "Number of scroll clicks (1-10, default 3)"},
        },
        "required": ["direction"],
    },
)
async def scroll_screen_tool(input_data: dict[str, Any]) -> str:
    direction = input_data["direction"].lower()
    amount = min(10, max(1, input_data.get("amount", 3)))
    # Negative = down, positive = up in mouse_event
    scroll_value = 120 * amount if direction == "up" else -120 * amount
    script = f"""
    Add-Type @"
    using System; using System.Runtime.InteropServices;
    public class ScrollMouse {{
        [DllImport("user32.dll")] public static extern void mouse_event(int dwFlags, int dx, int dy, int dwData, int dwExtraInfo);
    }}
"@
    [ScrollMouse]::mouse_event(0x0800, 0, 0, {scroll_value}, 0)
    Write-Output "Scrolled {direction} by {amount}"
    """
    return await run_powershell(script)


@tool(
    name="navigate_menu",
    description="Open and navigate application menus. Use when user says 'open File menu', 'go to Settings', 'open Edit menu'.",
    input_schema={
        "type": "object",
        "properties": {
            "menu_path": {"type": "string", "description": "Menu to open like 'File', 'Edit > Find', 'Settings'"},
        },
        "required": ["menu_path"],
    },
)
async def navigate_menu_tool(input_data: dict[str, Any]) -> str:
    menu = input_data["menu_path"]
    # Try keyboard shortcut first for common menus
    shortcuts = {
        "file": "%f", "edit": "%e", "view": "%v",
        "help": "%h", "tools": "%t", "settings": "%,",
    }
    first_menu = menu.split(">")[0].strip().lower()
    if first_menu in shortcuts:
        script = f"""
        Add-Type -AssemblyName System.Windows.Forms
        [System.Windows.Forms.SendKeys]::SendWait('{shortcuts[first_menu]}')
        Write-Output "Opened {first_menu} menu"
        """
        result = await run_powershell(script)
        # If there's a sub-menu, navigate to it
        parts = menu.split(">")
        if len(parts) > 1:
            await asyncio.sleep(0.5)
            sub = parts[1].strip()
            # Type first letter to jump to it
            script2 = f"""
            Add-Type -AssemblyName System.Windows.Forms
            [System.Windows.Forms.SendKeys]::SendWait('{sub[0].lower()}')
            [System.Windows.Forms.SendKeys]::SendWait('{{ENTER}}')
            Write-Output "Selected {sub}"
            """
            await run_powershell(script2)
        return f"Navigated to: {menu}"
    else:
        # Use vision to find and click the menu
        path = await _take_screenshot_temp()
        result = await vision_find_element(path, f"menu item or button labeled '{menu}'")
        if result.get("found"):
            await _click_at(result["x"], result["y"])
            return f"Clicked menu: {menu}"
        return f"Could not find menu: {menu}"
