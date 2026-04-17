"""Exercise Form Correction — webcam + AI vision to check workout form.

Uses the laptop webcam to capture snapshots during exercise,
then analyzes body position with Claude Vision to give form corrections.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import tempfile
from typing import Any

from app.tools.registry import tool
from app.tools.system import run_powershell
from app.llm import vision_analyze

log = logging.getLogger("jarvis.tools.exercise")


async def _capture_webcam() -> str:
    """Capture a frame from the webcam and return the temp file path."""
    path = tempfile.mktemp(suffix=".jpg")
    # Use PowerShell to capture webcam frame
    script = f"""
    Add-Type -AssemblyName System.Windows.Forms
    Add-Type @"
    using System;
    using System.Runtime.InteropServices;
    using System.Drawing;
    using System.Drawing.Imaging;

    public class WebcamCapture {{
        [DllImport("avicap32.dll")] public static extern IntPtr capCreateCaptureWindowA(string lpszWindowName, int dwStyle, int x, int y, int nWidth, int nHeight, IntPtr hWndParent, int nID);
        [DllImport("user32.dll")] public static extern bool SendMessage(IntPtr hWnd, uint Msg, int wParam, int lParam);
        [DllImport("user32.dll")] public static extern bool DestroyWindow(IntPtr hWnd);

        public static void Capture(string path) {{
            IntPtr hwnd = capCreateCaptureWindowA("cap", 0, 0, 0, 640, 480, IntPtr.Zero, 0);
            SendMessage(hwnd, 0x40a, 0, 0); // WM_CAP_DRIVER_CONNECT
            System.Threading.Thread.Sleep(500);
            SendMessage(hwnd, 0x41e, 0, 0); // WM_CAP_GRAB_FRAME
            SendMessage(hwnd, 0x419, 0, 0); // WM_CAP_FILE_SAVEDIB
            DestroyWindow(hwnd);
        }}
    }}
"@
    # Alternative: Use ffmpeg if available
    $ffmpeg = Get-Command ffmpeg -ErrorAction SilentlyContinue
    if ($ffmpeg) {{
        & ffmpeg -f dshow -i video="Integrated Camera" -frames:v 1 -y "{path}" 2>$null
        if (Test-Path "{path}") {{ Write-Output "{path}" }} else {{ Write-Output "FAIL" }}
    }} else {{
        # Fallback: take screenshot (shows webcam if open)
        Add-Type -AssemblyName System.Drawing
        $screen = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
        $bitmap = New-Object System.Drawing.Bitmap($screen.Width, $screen.Height)
        $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
        $graphics.CopyFromScreen($screen.Location, [System.Drawing.Point]::Empty, $screen.Size)
        $bitmap.Save("{path}")
        $graphics.Dispose()
        $bitmap.Dispose()
        Write-Output "{path}"
    }}
    """
    result = await run_powershell(script)
    return result.strip()


@tool(
    name="check_exercise_form",
    description="Check exercise form using the webcam/screen. Takes a snapshot and analyzes body position for correct form. Use when user says 'check my form', 'am I doing this right', 'watch my exercise', 'correct my pushup form'.",
    input_schema={
        "type": "object",
        "properties": {
            "exercise": {"type": "string", "description": "Name of the exercise: pushup, squat, plank, lunge, bicep curl, deadlift, etc."},
        },
        "required": ["exercise"],
    },
)
async def check_exercise_form_tool(input_data: dict[str, Any]) -> str:
    exercise = input_data["exercise"]

    # Capture image
    img_path = await _capture_webcam()
    if not img_path or "FAIL" in img_path:
        return "Could not capture image from webcam. Make sure your camera is working."

    prompt = f"""You are a professional fitness trainer. The user is performing: {exercise}.

Analyze their body position in this image and provide:
1. Is their form correct or incorrect?
2. What specific corrections do they need?
3. Common mistakes to avoid for this exercise
4. A quick tip to improve

Keep it short and actionable — this is spoken aloud during a workout.
No markdown formatting. Just natural speech."""

    result = await vision_analyze(img_path, prompt)
    return result


@tool(
    name="exercise_guide",
    description="Get a quick exercise guide — how to do an exercise with correct form. Use when user says 'how to do pushups', 'teach me squats', 'what is correct plank form'.",
    input_schema={
        "type": "object",
        "properties": {
            "exercise": {"type": "string", "description": "Name of the exercise"},
        },
        "required": ["exercise"],
    },
)
async def exercise_guide_tool(input_data: dict[str, Any]) -> str:
    exercise = input_data["exercise"]
    # This doesn't need vision — just knowledge
    return f"""Here's how to do {exercise} with correct form:

For a proper {exercise}:
- Start position, movement, and end position
- Key points: keep core tight, breathe properly, control the movement
- Common mistakes: rushing, poor alignment, holding breath

Ask me to 'check my form' while you're doing it and I'll use the camera to give you specific corrections."""


@tool(
    name="workout_timer",
    description="Start a workout timer — counts down for exercise sets and rest periods. Use when user says 'start 30 second plank timer', 'time my set', 'rest timer 60 seconds'.",
    input_schema={
        "type": "object",
        "properties": {
            "seconds": {"type": "integer", "description": "Timer duration in seconds"},
            "label": {"type": "string", "description": "What this timer is for (e.g., 'plank', 'rest', 'set')"},
        },
        "required": ["seconds"],
    },
)
async def workout_timer_tool(input_data: dict[str, Any]) -> str:
    seconds = input_data["seconds"]
    label = input_data.get("label", "exercise")

    # Use PowerShell to show a notification after the timer
    script = f"""
    Start-Sleep -Seconds {seconds}
    Add-Type -AssemblyName System.Windows.Forms
    [System.Windows.Forms.MessageBox]::Show('Time is up! {label} complete.', 'JARVIS Workout Timer', 'OK', 'Information')
    Write-Output "Timer done"
    """
    # Run in background so JARVIS doesn't block
    asyncio.create_task(asyncio.to_thread(lambda: __import__('subprocess').run(
        ["powershell.exe", "-NoProfile", "-Command", script],
        capture_output=True, text=True, timeout=seconds + 10
    )))

    return f"Timer started: {seconds} seconds for {label}. I'll notify you when it's done."
