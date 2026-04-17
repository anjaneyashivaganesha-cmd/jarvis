"""JARVIS Backend — FastAPI + WebSocket server with full AI pipeline."""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import memory
from app.llm import chat, chat_stream
from app.tts import synthesize
from app.tools.registry import execute_tool, get_tool_schemas
from app.voice_auth import enroll_voice, verify_voice, load_voiceprint, is_auth_enabled, disable_auth
from app.whisper_stt import transcribe_audio, preload_model

# Import tools to register them
import app.tools.notes  # noqa: F401
import app.tools.system  # noqa: F401
import app.tools.productivity  # noqa: F401
import app.tools.information  # noqa: F401
import app.tools.media  # noqa: F401
import app.tools.files  # noqa: F401
import app.tools.habitat  # noqa: F401
import app.tools.filmmaker  # noqa: F401
import app.tools.vision  # noqa: F401
import app.tools.automation  # noqa: F401
import app.tools.persistent_memory  # noqa: F401
import app.tools.integrations  # noqa: F401
import app.tools.exercise  # noqa: F401
import app.tools.camera  # noqa: F401
import app.tools.workout  # noqa: F401

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("jarvis")

# --- Personality modes ---
PERSONALITIES = {
    "default": "Speak in a refined British manner like the MCU JARVIS. Be witty but professional. Address user as 'sir' occasionally.",
    "casual": "Be casual and friendly, like a chill buddy. Use informal language, contractions, slang.",
    "formal": "Be extremely formal and professional. No humor, precise language.",
    "funny": "Be hilarious. Add jokes, puns, and witty remarks to every response. Still be helpful.",
    "pirate": "Talk like a pirate. Arrr! But still be helpful and answer correctly.",
}

_current_personality = "default"

# --- Command history ---
_command_history: list[dict] = []


def _get_context_prompt() -> str:
    """Generate context-aware prompt additions based on time of day."""
    now = datetime.now()
    hour = now.hour
    if hour < 6:
        time_context = "It's very late at night/early morning. Be gentle, the user might be tired."
    elif hour < 12:
        time_context = "It's morning. Be energetic and positive."
    elif hour < 17:
        time_context = "It's afternoon."
    elif hour < 21:
        time_context = "It's evening."
    else:
        time_context = "It's night time. Be calm."

    personality = PERSONALITIES.get(_current_personality, PERSONALITIES["default"])
    return f"{personality} {time_context} Current time: {now.strftime('%I:%M %p')}, Date: {now.strftime('%A, %B %d, %Y')}."


@asynccontextmanager
async def lifespan(app: FastAPI):
    await memory.init_db()
    load_voiceprint()
    log.info("JARVIS online")
    yield
    await memory.close_db()
    log.info("JARVIS offline")


app = FastAPI(title="JARVIS", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "jarvis", "tools": len(get_tool_schemas())}


@app.get("/api/personality")
async def get_personality():
    return {"current": _current_personality, "available": list(PERSONALITIES.keys())}


@app.post("/api/personality/{mode}")
async def set_personality(mode: str):
    global _current_personality
    if mode in PERSONALITIES:
        _current_personality = mode
        return {"status": "ok", "personality": mode}
    return JSONResponse(status_code=400, content={"error": f"Unknown personality: {mode}"})


@app.get("/api/history")
async def get_history():
    return {"commands": _command_history[-50:]}


async def process_message(user_text: str) -> dict:
    """Process a user message through the full AI pipeline."""
    # Record in command history
    _command_history.append({
        "text": user_text,
        "time": datetime.now().strftime("%I:%M %p"),
    })

    # Check for personality switch commands
    global _current_personality
    lower = user_text.lower().strip()
    for mode in PERSONALITIES:
        if f"switch to {mode}" in lower or f"{mode} mode" in lower or f"be {mode}" in lower:
            _current_personality = mode
            return {"text": f"Personality switched to {mode} mode, sir.", "audio": None}

    # Check for "what did I ask" / command history queries
    if "what did i ask" in lower or "command history" in lower or "last command" in lower:
        if _command_history:
            recent = _command_history[-5:]
            lines = [f"- {c['text']} ({c['time']})" for c in recent]
            return {"text": "Your recent commands:\n" + "\n".join(lines), "audio": None}

    # Check for "summarize" our conversation
    if "summarize" in lower and ("conversation" in lower or "chat" in lower):
        recent = await memory.get_recent_messages(limit=10)
        if recent:
            summary_parts = [f"{m['role']}: {m['content'][:80]}" for m in recent[-6:]]
            return {"text": "Recent conversation summary:\n" + "\n".join(summary_parts), "audio": None}

    # Save user message
    await memory.save_message("user", user_text)

    # Build conversation context from memory
    recent = await memory.get_recent_messages(limit=20)
    messages = [{"role": m["role"], "content": m["content"]} for m in recent]

    if not messages or messages[-1]["content"] != user_text:
        messages.append({"role": "user", "content": user_text})

    # Get tool schemas
    tools = get_tool_schemas()

    # Call LLM with context-aware personality
    result = await chat(messages, tools=tools if tools else None, extra_system=_get_context_prompt())
    response_text = result.get("text", "")

    # Handle tool calls — FAST PATH: skip second API call for simple tools
    tool_calls = result.get("tool_calls", [])
    if tool_calls:
        tool_outputs = []
        for tc in tool_calls:
            tool_output = await execute_tool(tc["name"], tc["input"])
            tool_outputs.append(tool_output)
            log.info("Tool %s → %s", tc["name"], tool_output[:100])

        # For simple tool results, just use the output directly (saves 1 API call = 2x faster)
        combined_output = "\n".join(tool_outputs)
        if response_text:
            response_text = f"{response_text} {combined_output}"
        else:
            response_text = combined_output

    # Save assistant response
    await memory.save_message("assistant", response_text)

    # Generate TTS
    audio_b64 = await synthesize(response_text) if response_text else None

    return {
        "text": response_text,
        "audio": audio_b64,
    }


async def _check_quick_command(text: str) -> dict | None:
    """Check for quick commands that don't need LLM. Returns result dict or None."""
    global _current_personality
    lower = text.lower().strip()

    # Personality switch
    for mode in PERSONALITIES:
        if f"switch to {mode}" in lower or f"{mode} mode" in lower or f"be {mode}" in lower:
            _current_personality = mode
            return {"text": f"Personality switched to {mode} mode, sir."}

    # Command history
    if "what did i ask" in lower or "command history" in lower or "last command" in lower:
        if _command_history:
            recent = _command_history[-5:]
            lines = [f"{c['text']} at {c['time']}" for c in recent]
            return {"text": "Your recent commands: " + ", ".join(lines)}

    # Conversation summary
    if "summarize" in lower and ("conversation" in lower or "chat" in lower):
        recent = await memory.get_recent_messages(limit=10)
        if recent:
            summary_parts = [f"{m['role']}: {m['content'][:80]}" for m in recent[-6:]]
            return {"text": "Recent conversation summary: " + ". ".join(summary_parts)}

    # Orb theme switch
    valid_themes = ["iron_man", "matrix", "ocean", "fire", "minimal", "cyberpunk"]
    for theme in valid_themes:
        theme_name = theme.replace("_", " ")
        if f"{theme_name} theme" in lower or f"{theme_name} mode" in lower or f"theme {theme_name}" in lower or f"switch to {theme_name}" in lower:
            return {"text": f"Switching to {theme_name} theme, sir.", "theme": theme}

    return None


import re

# Backend speech correction — fixes common voice recognition errors
_SPEECH_FIXES = [
    (r"\bcloud\b", "Claude"), (r"\bclod\b", "Claude"), (r"\bclawed\b", "Claude"),
    (r"\bservice\b", "JARVIS"), (r"\bjarvas\b", "JARVIS"), (r"\bjervis\b", "JARVIS"),
    (r"\bnote\s*pad\b", "Notepad"), (r"\bnot pad\b", "Notepad"), (r"\bno pad\b", "Notepad"),
    (r"\bcrome\b", "Chrome"), (r"\bscreen\s*shot\b", "screenshot"), (r"\bscreen\s*shut\b", "screenshot"),
    (r"\bdesk\s*top\b", "desktop"), (r"\bwall\s*paper\b", "wallpaper"),
    (r"\bblue\s*tooth\b", "Bluetooth"), (r"\bshut\s*down\b", "shutdown"),
    (r"\bwhats\s*app\b", "WhatsApp"), (r"\btele\s*gram\b", "Telegram"),
    (r"\bvisa?\s*code\b", "VS Code"), (r"\bbe as code\b", "VS Code"),
    (r"\bclothes\b", "close"), (r"\bclause\b", "close"),
    (r"\bgreat a\b", "create a"), (r"\blunch\b", "launch"),
]


def _fix_transcript(text: str) -> str:
    """Fix common speech recognition errors before LLM processing."""
    fixed = text
    for pattern, replacement in _SPEECH_FIXES:
        fixed = re.sub(pattern, replacement, fixed, flags=re.IGNORECASE)
    return fixed


async def process_message_stream(ws: WebSocket, user_text: str) -> None:
    """Process a user message with streaming responses via WebSocket."""
    # Fix speech recognition errors
    user_text = _fix_transcript(user_text)
    log.info("Corrected: %s", user_text)

    # Record in command history
    _command_history.append({
        "text": user_text,
        "time": datetime.now().strftime("%I:%M %p"),
    })

    # Save user message
    await memory.save_message("user", user_text)

    # Build conversation context
    recent = await memory.get_recent_messages(limit=20)
    messages = [{"role": m["role"], "content": m["content"]} for m in recent]
    if not messages or messages[-1]["content"] != user_text:
        messages.append({"role": "user", "content": user_text})

    tools = get_tool_schemas()

    # Start streaming
    await ws.send_json({"type": "stream_start"})

    full_text = ""
    tool_calls: list[dict] = []

    async for chunk in chat_stream(messages, tools=tools if tools else None, extra_system=_get_context_prompt()):
        if chunk["type"] == "chunk":
            await ws.send_json({"type": "stream_chunk", "text": chunk["text"]})
            full_text += chunk["text"]
        elif chunk["type"] == "done":
            full_text = chunk.get("text", full_text)
            tool_calls = chunk.get("tool_calls", [])
        elif chunk["type"] == "full":
            # Non-streaming fallback (Ollama, cache hit)
            full_text = chunk.get("text", "")
            tool_calls = chunk.get("tool_calls", [])
            await ws.send_json({"type": "stream_chunk", "text": full_text})

    # Handle tool calls
    if tool_calls:
        tool_outputs = []
        for tc in tool_calls:
            log.info("Calling tool: %s with input: %s", tc["name"], str(tc["input"])[:200])
            tool_output = await execute_tool(tc["name"], tc["input"])
            tool_outputs.append(tool_output)
            log.info("Tool %s → %s", tc["name"], tool_output[:200])

        combined = "\n".join(tool_outputs)
        tool_text = f" {combined}" if full_text else combined
        full_text = f"{full_text}{tool_text}" if full_text else combined
        await ws.send_json({"type": "stream_chunk", "text": tool_text})

    # Send stream end
    await ws.send_json({"type": "stream_end", "text": full_text})

    # Save to memory
    await memory.save_message("assistant", full_text)

    # Generate TTS and send audio separately
    audio_b64 = await synthesize(full_text) if full_text else None
    if audio_b64:
        await ws.send_json({"type": "audio", "audio": audio_b64})
    else:
        await ws.send_json({"type": "no_audio"})


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    log.info("Client connected")

    try:
        while True:
            raw = await ws.receive_text()
            data = json.loads(raw)
            msg_type = data.get("type")

            if msg_type == "transcript":
                text = _fix_transcript(data.get("text", "").strip())
                if not text:
                    continue

                # Voice verification — if enrolled, check voice before processing
                voice_audio = data.get("voice_audio", "")
                if is_auth_enabled() and voice_audio:
                    vr = verify_voice(voice_audio)
                    if not vr.get("verified"):
                        log.warning("Voice rejected: score=%.3f", vr.get("score", 0))
                        await ws.send_json({
                            "type": "response",
                            "text": "Voice not recognized. Access denied.",
                        })
                        continue

                log.info("User: %s", text)
                await ws.send_json({"type": "status", "text": "thinking"})

                try:
                    # Quick commands (personality, history, theme) — non-streaming
                    quick = await _check_quick_command(text)
                    if quick:
                        # Send theme change if present
                        if "theme" in quick:
                            await ws.send_json({"type": "theme", "theme": quick["theme"]})
                        audio_b64 = await synthesize(quick["text"]) if quick["text"] else None
                        resp: dict = {"type": "response", "text": quick["text"]}
                        if audio_b64:
                            resp["audio"] = audio_b64
                        await ws.send_json(resp)
                    else:
                        # Full streaming pipeline
                        await asyncio.wait_for(
                            process_message_stream(ws, text),
                            timeout=30.0,
                        )
                except asyncio.TimeoutError:
                    log.error("Process message timed out for: %s", text[:50])
                    await ws.send_json({"type": "response", "text": "Sorry sir, that took too long. Please try again."})
                except Exception as e:
                    log.exception("Process message error")
                    await ws.send_json({"type": "response", "text": f"I encountered an error, sir. {str(e)[:80]}"})

            elif msg_type == "ping":
                await ws.send_json({"type": "pong"})

            elif msg_type == "set_personality":
                mode = data.get("mode", "default")
                global _current_personality
                if mode in PERSONALITIES:
                    _current_personality = mode
                    await ws.send_json({"type": "response", "text": f"Personality set to {mode}."})

            elif msg_type == "enroll_voice":
                audio_b64 = data.get("audio", "")
                result = enroll_voice(audio_b64)
                await ws.send_json({"type": "voice_auth_result", **result})

            elif msg_type == "verify_voice":
                audio_b64 = data.get("audio", "")
                result = verify_voice(audio_b64)
                await ws.send_json({"type": "voice_verify_result", **result})

            elif msg_type == "disable_voice_auth":
                disable_auth()
                await ws.send_json({"type": "response", "text": "Voice authentication disabled."})

    except WebSocketDisconnect:
        log.info("Client disconnected")
    except Exception:
        log.exception("WebSocket error")
