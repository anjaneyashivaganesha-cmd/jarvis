"""Camera tools — webcam access, capture, face detection, AI analysis.

Gives JARVIS eyes through the laptop webcam using OpenCV + Claude Vision.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import tempfile
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from app.tools.registry import tool
from app.llm import vision_analyze

log = logging.getLogger("jarvis.tools.camera")


async def _capture_webcam_frame(save_path: str = "") -> str:
    """Capture a single frame from the webcam. Returns file path."""
    def _capture():
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            return ""
        # Let camera warm up
        for _ in range(5):
            cap.read()
        ret, frame = cap.read()
        cap.release()
        if not ret:
            return ""
        path = save_path or tempfile.mktemp(suffix=".jpg")
        cv2.imwrite(path, frame)
        return path

    return await asyncio.to_thread(_capture)


async def _capture_webcam_base64() -> str:
    """Capture webcam frame and return as base64."""
    def _capture():
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            return ""
        for _ in range(5):
            cap.read()
        ret, frame = cap.read()
        cap.release()
        if not ret:
            return ""
        _, buffer = cv2.imencode('.jpg', frame)
        return base64.b64encode(buffer).decode()

    return await asyncio.to_thread(_capture)


@tool(
    name="camera_capture",
    description="Take a photo using the laptop webcam. Saves to desktop or specified path. Use when user says 'take a photo', 'capture from camera', 'take my picture', 'use webcam'.",
    input_schema={
        "type": "object",
        "properties": {
            "save_to": {"type": "string", "description": "Where to save: 'desktop', 'documents', or a full path. Default: desktop"},
            "filename": {"type": "string", "description": "Filename (default: jarvis_photo_timestamp.jpg)"},
        },
    },
)
async def camera_capture_tool(input_data: dict[str, Any]) -> str:
    save_to = input_data.get("save_to", "desktop").lower()
    filename = input_data.get("filename", "")

    folder_map = {
        "desktop": "C:\\Users\\suche\\Desktop",
        "documents": "C:\\Users\\suche\\Documents",
        "downloads": "C:\\Users\\suche\\Downloads",
    }
    folder = folder_map.get(save_to, save_to)

    if not filename:
        from datetime import datetime
        filename = f"jarvis_photo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"

    full_path = f"{folder}\\{filename}"
    result = await _capture_webcam_frame(full_path)

    if result:
        return f"Photo captured and saved to {result}"
    return "Could not access webcam. Make sure camera is not in use by another app."


@tool(
    name="camera_look",
    description="Look through the webcam and describe what JARVIS sees. Use when user says 'what do you see through camera', 'look at me', 'who is in front of the camera', 'what is this object'.",
    input_schema={
        "type": "object",
        "properties": {
            "question": {"type": "string", "description": "What to look for or describe (default: describe everything visible)"},
        },
    },
)
async def camera_look_tool(input_data: dict[str, Any]) -> str:
    question = input_data.get("question", "Describe what you see through this webcam. Mention people, objects, environment, and anything notable.")

    path = await _capture_webcam_frame()
    if not path:
        return "Could not access webcam."

    result = await vision_analyze(path, question)
    # Clean up temp file
    Path(path).unlink(missing_ok=True)
    return result


@tool(
    name="camera_detect_faces",
    description="Detect faces through the webcam and count how many people are visible. Use when user says 'how many people are here', 'detect faces', 'is anyone there'.",
    input_schema={"type": "object", "properties": {}},
)
async def camera_detect_faces_tool(input_data: dict[str, Any]) -> str:
    def _detect():
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            return "Could not access webcam."
        for _ in range(5):
            cap.read()
        ret, frame = cap.read()
        cap.release()
        if not ret:
            return "Could not capture frame."

        # Use OpenCV's built-in face detector
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))

        count = len(faces)
        if count == 0:
            return "No faces detected in the camera view."
        elif count == 1:
            return "I can see 1 person in front of the camera."
        else:
            return f"I can see {count} people in front of the camera."

    return await asyncio.to_thread(_detect)


@tool(
    name="camera_identify_object",
    description="Point something at the camera and JARVIS will identify it. Use when user says 'what is this', 'identify this object', 'what am I holding'.",
    input_schema={
        "type": "object",
        "properties": {
            "hint": {"type": "string", "description": "Optional hint about what kind of object (food, electronics, clothing, etc.)"},
        },
    },
)
async def camera_identify_object_tool(input_data: dict[str, Any]) -> str:
    hint = input_data.get("hint", "")

    path = await _capture_webcam_frame()
    if not path:
        return "Could not access webcam."

    prompt = f"Identify the main object or thing visible in this webcam image. What is it? Give a clear, concise identification."
    if hint:
        prompt += f" Hint: it might be related to {hint}."

    result = await vision_analyze(path, prompt)
    Path(path).unlink(missing_ok=True)
    return result


@tool(
    name="camera_read_text",
    description="Point a document, book, or sign at the camera and JARVIS reads the text. Use when user says 'read this paper', 'what does this say', 'scan this document'.",
    input_schema={"type": "object", "properties": {}},
)
async def camera_read_text_tool(input_data: dict[str, Any]) -> str:
    path = await _capture_webcam_frame()
    if not path:
        return "Could not access webcam."

    result = await vision_analyze(path, "Read ALL the text visible in this image. If it's a document, paper, book, or sign, transcribe the text exactly. Focus on the text content.")
    Path(path).unlink(missing_ok=True)
    return result


@tool(
    name="camera_check_form",
    description="Check exercise form using webcam. Takes a snapshot and analyzes body position. Use when user says 'check my form', 'am I doing this right', 'watch my pushups'.",
    input_schema={
        "type": "object",
        "properties": {
            "exercise": {"type": "string", "description": "Name of the exercise: pushup, squat, plank, lunge, bicep curl, deadlift, etc."},
        },
        "required": ["exercise"],
    },
)
async def camera_check_form_tool(input_data: dict[str, Any]) -> str:
    exercise = input_data["exercise"]

    path = await _capture_webcam_frame()
    if not path:
        return "Could not access webcam. Make sure camera is not blocked."

    prompt = f"""You are a professional fitness trainer. The user is performing: {exercise}.

Analyze their body position and give:
1. Is the form correct or not?
2. What specific corrections needed?
3. One quick tip to improve.

Keep it short — this is spoken during a workout. No markdown."""

    result = await vision_analyze(path, prompt)
    Path(path).unlink(missing_ok=True)
    return result
