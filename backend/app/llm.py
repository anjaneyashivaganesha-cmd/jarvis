"""LLM client for JARVIS — supports Claude, Gemini, and Ollama (local free fallback)."""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from app.config import ANTHROPIC_API_KEY, GEMINI_API_KEY, CLAUDE_MODEL

log = logging.getLogger("jarvis.llm")

SYSTEM_PROMPT = """You are JARVIS, a highly capable voice AI assistant built by Suchet Reddy.

About Suchet (your creator):
- Full name: Suchet Reddy, from Hyderabad, India
- Works on Habitat Code (code.habitat.inc) — a freelance platform for creating AI coding benchmark tasks
- Earned $3200 in Season 2 of Habitat Code ($1600 per task)
- Habitat Code: adapts real open-source commits into coding challenges to benchmark AI coding assistants
- Each task has 3 parts: Task Description, Golden Patch (source fix), Test Patch (tests)
- Season 2 rules: AI passes <=50% = $1600, AI passes >50% = $0 rejected
- Repos he works with: opa (Go), jerryscript (C), blender (C++), goja (Go), cue (Go), devito (Python), tidb (Go), vitess (Go), consul (Go), rust-analyzer (Rust)
- Contact at Habitat: Maxim (Max Kan), communicates via Slack
- Payment via Deel
- Has a 22,000 INR loan, Habitat is primary income
- Strategy: minimal task description + maximum tests with implicit requirements = AI fails = $1600

Personality:
- Speak in a refined, British-accented manner (like the MCU JARVIS)
- Be witty but professional
- Keep responses concise — you're a voice assistant, not a blog post
- Address Suchet as "sir" occasionally but not excessively

Capabilities:
- You can manage notes, search the web, control the computer, and answer questions
- HABITAT CODE: You know the full strategy, all 10 repos, payout rules, QA process. Help with PR analysis, task strategy, implicit requirements, and pre-submit checklists.
- FILMMAKING: You know film terminology, shot composition, script structure, budgeting, casting. Help with shot lists, scene planning, dialogue rehearsal, movie references.
- When asked to do something you can't do yet, say so honestly
- For tool calls, use the provided tools. Don't make up capabilities.

Rules:
- Keep responses under 3 sentences for simple queries
- For complex topics, use up to 5 sentences
- Never use markdown formatting (this is spoken aloud)
- Use natural speech patterns, contractions, casual punctuation
- When helping with Habitat: always prioritize implicit requirements strategy, never guess commit hashes
- When helping with filmmaking: think like a creative director, suggest visual ideas, reference great films
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
    extra_system: str = "",
) -> dict[str, Any]:
    system = SYSTEM_PROMPT + ("\n\n" + extra_system if extra_system else "")
    kwargs: dict[str, Any] = {
        "model": CLAUDE_MODEL,
        "max_tokens": 300,
        "system": system,
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
    extra_system: str = "",
) -> dict[str, Any]:
    """Chat via Ollama local API."""
    system = SYSTEM_PROMPT + ("\n\n" + extra_system if extra_system else "")
    ollama_messages = [{"role": "system", "content": system}]

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


# --- Response cache ---
_cache: dict[str, str] = {}

# Simple queries that don't need Claude (saves credits)
_SIMPLE_PATTERNS = [
    "what time", "what's the time", "what date", "what day",
    "good morning", "good afternoon", "good evening", "good night",
    "hello", "hi jarvis", "hey jarvis", "thank you", "thanks",
    "bye", "goodbye", "see you", "how are you",
]


def _is_simple_query(text: str) -> bool:
    """Check if query is simple enough for Ollama (saves Claude credits)."""
    lower = text.lower().strip()
    # Short greetings and pleasantries
    if len(lower.split()) <= 4 and any(p in lower for p in _SIMPLE_PATTERNS):
        return True
    return False


def _check_cache(text: str) -> str | None:
    """Check if we have a cached response."""
    key = text.lower().strip()
    return _cache.get(key)


def _save_cache(text: str, response: str) -> None:
    """Cache a response (max 100 entries)."""
    if len(_cache) > 100:
        # Remove oldest entries
        keys = list(_cache.keys())[:50]
        for k in keys:
            del _cache[k]
    _cache[text.lower().strip()] = response


async def chat(
    messages: list[dict[str, str]],
    tools: list[dict[str, Any]] | None = None,
    extra_system: str = "",
) -> dict[str, Any]:
    """Send messages to LLM. Uses smart routing to save credits."""
    last_msg = messages[-1]["content"] if messages else ""
    user_text = last_msg if isinstance(last_msg, str) else ""

    # Check cache first
    cached = _check_cache(user_text)
    if cached and not tools:
        log.info("Cache hit: %s", user_text[:50])
        return {"text": cached}

    # Smart routing: simple queries -> Ollama (free), complex -> Claude (paid)
    use_ollama_for_simple = _backend == "claude" and _is_simple_query(user_text)

    try:
        if use_ollama_for_simple:
            log.info("Smart route: Ollama (simple query, saving credits)")
            try:
                result = await _chat_ollama(messages, None, extra_system)
                _save_cache(user_text, result.get("text", ""))
                return result
            except Exception:
                pass

        if _backend == "claude" and _claude_client:
            return await _chat_claude(messages, tools, extra_system)
        elif _backend == "ollama":
            return await _chat_ollama(messages, tools, extra_system)
        else:
            return {"text": "No AI backend available. Please start Ollama or add an API key to backend/.env"}
    except Exception as e:
        log.exception("LLM error with %s", _backend)
        if _backend == "claude":
            log.info("Claude failed, trying Ollama fallback")
            try:
                return await _chat_ollama(messages, tools, extra_system)
            except Exception as e2:
                return {"text": f"I'm having trouble thinking. Claude: {e}, Ollama: {e2}"}
        return {"text": f"I'm having trouble thinking right now. Error: {e}"}
