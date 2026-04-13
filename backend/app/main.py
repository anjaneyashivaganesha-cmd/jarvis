"""JARVIS Backend — FastAPI + WebSocket server with Claude Haiku, TTS, and tools."""

from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app import memory
from app.llm import chat
from app.tts import synthesize
from app.tools.registry import execute_tool, get_tool_schemas

# Import tools to register them
import app.tools.notes  # noqa: F401
import app.tools.system  # noqa: F401

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("jarvis")


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
    return {"status": "ok", "service": "jarvis"}


async def process_message(user_text: str) -> dict:
    """Process a user message through Claude Haiku with tools and memory."""
    # Save user message
    await memory.save_message("user", user_text)

    # Build conversation context from memory
    recent = await memory.get_recent_messages(limit=20)
    messages = [{"role": m["role"], "content": m["content"]} for m in recent]

    # If no recent messages (fresh start), add the current one
    if not messages or messages[-1]["content"] != user_text:
        messages.append({"role": "user", "content": user_text})

    # Get tool schemas
    tools = get_tool_schemas()

    # Call Claude
    result = await chat(messages, tools=tools if tools else None)
    response_text = result.get("text", "")

    # Handle tool calls
    tool_calls = result.get("tool_calls", [])
    if tool_calls:
        # Execute each tool and collect results
        tool_results = []
        for tc in tool_calls:
            tool_output = await execute_tool(tc["name"], tc["input"])
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tc["id"],
                "content": tool_output,
            })
            log.info("Tool %s → %s", tc["name"], tool_output[:100])

        # Send tool results back to Claude for a natural response
        messages.append({"role": "assistant", "content": result.get("raw_content", response_text)})
        messages.append({"role": "user", "content": json.dumps(tool_results)})

        # Build assistant message with tool_use blocks for proper API format
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
        followup_messages = messages[:-2]  # Remove the two we just added
        followup_messages.append({"role": "assistant", "content": assistant_content})
        followup_messages.append({"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": tc["id"], "content": tool_output}
            for tc, tool_output in zip(tool_calls, [tr["content"] for tr in tool_results])
        ]})

        followup = await chat(followup_messages)
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

                # Send "thinking" status
                await ws.send_json({"type": "status", "text": "thinking"})

                # Process through Claude + tools + TTS
                result = await process_message(text)

                # Send response
                response: dict = {
                    "type": "response",
                    "text": result["text"],
                }
                if result.get("audio"):
                    response["audio"] = result["audio"]

                await ws.send_json(response)

            elif msg_type == "ping":
                await ws.send_json({"type": "pong"})

    except WebSocketDisconnect:
        log.info("Client disconnected")
    except Exception:
        log.exception("WebSocket error")
