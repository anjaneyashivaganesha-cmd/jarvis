"""JARVIS Backend — FastAPI + WebSocket server with full AI pipeline."""

from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import memory
from app.llm import chat
from app.tts import synthesize
from app.tools.registry import execute_tool, get_tool_schemas

# Import tools to register them
import app.tools.notes  # noqa: F401
import app.tools.system  # noqa: F401
import app.tools.productivity  # noqa: F401
import app.tools.information  # noqa: F401
import app.tools.media  # noqa: F401
import app.tools.files  # noqa: F401

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

    # Handle tool calls
    tool_calls = result.get("tool_calls", [])
    if tool_calls:
        tool_results = []
        for tc in tool_calls:
            tool_output = await execute_tool(tc["name"], tc["input"])
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tc["id"],
                "content": tool_output,
            })
            log.info("Tool %s → %s", tc["name"], tool_output[:100])

        # Build assistant message with tool_use blocks
        assistant_content = []
        if response_text:
            assistant_content.append({"type": "text", "text": response_text})
        for tc in tool_calls:
            assistant_content.append({
                "type": "tool_use",
                "id": tc["id"],
                "name": tc["name"],
                "input": tc["input"],
            })

        # Rebuild messages with proper tool use/result format
        followup_messages = messages.copy()
        followup_messages.append({"role": "assistant", "content": assistant_content})
        followup_messages.append({"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": tc["id"], "content": tool_output}
            for tc, tool_output in zip(tool_calls, [tr["content"] for tr in tool_results])
        ]})

        followup = await chat(followup_messages, extra_system=_get_context_prompt())
        response_text = followup.get("text", response_text)

    # Save assistant response
    await memory.save_message("assistant", response_text)

    # Generate TTS
    audio_b64 = await synthesize(response_text) if response_text else None

    return {
        "text": response_text,
        "audio": audio_b64,
    }


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
                text = data.get("text", "").strip()
                if not text:
                    continue

                log.info("User: %s", text)
                await ws.send_json({"type": "status", "text": "thinking"})

                result = await process_message(text)

                response: dict = {
                    "type": "response",
                    "text": result["text"],
                }
                if result.get("audio"):
                    response["audio"] = result["audio"]

                await ws.send_json(response)

            elif msg_type == "ping":
                await ws.send_json({"type": "pong"})

            elif msg_type == "set_personality":
                mode = data.get("mode", "default")
                global _current_personality
                if mode in PERSONALITIES:
                    _current_personality = mode
                    await ws.send_json({"type": "response", "text": f"Personality set to {mode}."})

    except WebSocketDisconnect:
        log.info("Client disconnected")
    except Exception:
        log.exception("WebSocket error")
