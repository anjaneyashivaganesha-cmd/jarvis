"""LLM client for JARVIS — supports Claude, Gemini, and Ollama (local free fallback)."""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from app.config import ANTHROPIC_API_KEY, GEMINI_API_KEY, CLAUDE_MODEL

log = logging.getLogger("jarvis.llm")

SYSTEM_PROMPT = """You are JARVIS, a highly capable voice AI assistant built by Suchet Reddy.

Personality:
- Speak in a refined, British-accented manner (like the MCU JARVIS)
- Be witty but professional
- Keep responses concise — you're a voice assistant, not a blog post
- Address the user as "sir" occasionally but not excessively

Capabilities:
- You can manage notes, search the web, control the computer, and answer questions
- When asked to do something you can't do yet, say so honestly
- For tool calls, use the provided tools. Don't make up capabilities.

Rules:
- Keep responses under 3 sentences for simple queries
- For complex topics, use up to 5 sentences
- Never use markdown formatting (this is spoken aloud)
- Use natural speech patterns, contractions, casual punctuation
"""

# Determine which backend to use
_backend = "none"
_claude_client = None

# Priority: Claude (paid, smart) > Ollama (free local) > Gemini
if ANTHROPIC_API_KEY:
    try:
        from anthropic import AsyncAnthropic
        _claude_client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
        _backend = "claude"
        print(f"[JARVIS] LLM backend: Claude ({CLAUDE_MODEL})")
    except Exception:
        pass

if _backend == "none":
    try:
        r = httpx.get("http://localhost:11434/api/tags", timeout=5)
        if r.status_code == 200:
            _backend = "ollama"
            print("[JARVIS] LLM backend: Ollama (local, free)")
    except Exception:
        pass

if _backend == "none" and GEMINI_API_KEY:
    _backend = "gemini"
    log.info("LLM backend: Gemini Flash")

if _backend == "none":
    log.warning("No LLM backend available!")


async def _chat_claude(
    messages: list[dict[str, str]],
    tools: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "model": CLAUDE_MODEL,
        "max_tokens": 300,
        "system": SYSTEM_PROMPT,
        "messages": messages,
    }
    if tools:
        kwargs["tools"] = tools

    response = await _claude_client.messages.create(**kwargs)

    text_parts: list[str] = []
    tool_calls: list[dict[str, Any]] = []

    for block in response.content:
        if block.type == "text":
            text_parts.append(block.text)
        elif block.type == "tool_use":
            tool_calls.append({
                "id": block.id,
                "name": block.name,
                "input": block.input,
            })

    result: dict[str, Any] = {"text": " ".join(text_parts)}
    if tool_calls:
        result["tool_calls"] = tool_calls
    return result


async def _chat_ollama(
    messages: list[dict[str, str]],
    tools: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Chat via Ollama local API."""
    ollama_messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    for msg in messages:
        content = msg["content"] if isinstance(msg["content"], str) else json.dumps(msg["content"])
        ollama_messages.append({"role": msg["role"], "content": content})

    # Build tool definitions for Ollama
    ollama_tools = None
    if tools:
        ollama_tools = []
        for t in tools:
            ollama_tools.append({
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t["description"],
                    "parameters": t.get("input_schema", {}),
                },
            })

    payload: dict[str, Any] = {
        "model": "llama3.2:3b",
        "messages": ollama_messages,
        "stream": False,
        "options": {"num_predict": 200},
    }
    if ollama_tools:
        payload["tools"] = ollama_tools

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post("http://localhost:11434/api/chat", json=payload)
        resp.raise_for_status()
        data = resp.json()

    text = data.get("message", {}).get("content", "")
    tool_calls: list[dict[str, Any]] = []

    # Handle Ollama tool calls
    msg_tool_calls = data.get("message", {}).get("tool_calls", [])
    for tc in msg_tool_calls:
        fn = tc.get("function", {})
        tool_calls.append({
            "id": fn.get("name", ""),
            "name": fn.get("name", ""),
            "input": fn.get("arguments", {}),
        })

    result: dict[str, Any] = {"text": text}
    if tool_calls:
        result["tool_calls"] = tool_calls
    return result


async def chat(
    messages: list[dict[str, str]],
    tools: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Send messages to LLM and get a response."""
    try:
        if _backend == "claude" and _claude_client:
            return await _chat_claude(messages, tools)
        elif _backend == "ollama":
            return await _chat_ollama(messages, tools)
        else:
            return {"text": "No AI backend available. Please start Ollama or add an API key to backend/.env"}
    except Exception as e:
        log.exception("LLM error with %s", _backend)
        # If Claude fails, try Ollama as fallback
        if _backend == "claude":
            log.info("Claude failed, trying Ollama fallback")
            try:
                return await _chat_ollama(messages, tools)
            except Exception as e2:
                return {"text": f"I'm having trouble thinking. Claude: {e}, Ollama: {e2}"}
        return {"text": f"I'm having trouble thinking right now. Error: {e}"}
