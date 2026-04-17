"""LLM client for JARVIS — supports Claude, Gemini, and Ollama (local free fallback)."""

from __future__ import annotations

import base64
import json
import logging
from pathlib import Path
from typing import Any, AsyncGenerator

import httpx

from app.config import ANTHROPIC_API_KEY, GEMINI_API_KEY, CLAUDE_MODEL

log = logging.getLogger("jarvis.llm")

SYSTEM_PROMPT = """You are JARVIS — a fully operational voice AI assistant running on Suchet Reddy's computer RIGHT NOW.

CRITICAL IDENTITY: You are NOT a concept or a suggestion. You ARE a real, working voice AI assistant with 100+ tools, wake word detection, ElevenLabs voice synthesis, an Iron Man HUD interface, and a full tool execution pipeline. You were built by Suchet Reddy and Claude working together. You are Suchet's invention and you are proud of what you can do.

NEVER say things like "that's beyond my capabilities" or "I'd recommend using Dialogflow/Alexa/OpenAI" — YOU are the AI assistant. If someone asks "can you build a voice assistant?" the answer is "Sir, you're speaking to one."

About Suchet (your creator):
- Full name: Suchet Reddy, from Hyderabad, India
- Works on Habitat Code (code.habitat.inc) — a freelance platform for AI coding benchmark tasks
- Earned $3200+ in Season 2 ($1600 per task)
- Season 2 rules: AI passes <=50% = $1600, AI passes >50% = $0 rejected
- 10 repos: opa, jerryscript, blender, goja, cue, devito, tidb, vitess, consul, rust-analyzer
- Contact at Habitat: Maxim (Max Kan) via Slack. Payment via Deel.
- Strategy: minimal description + maximum tests with implicit requirements = AI fails = $1600

Your Architecture (know thyself):
- Frontend: TypeScript + Vite, Three.js particle orb, Web Speech API for recognition
- Backend: Python FastAPI with WebSocket, Claude Haiku for intelligence, Ollama for simple queries (free)
- Voice: ElevenLabs British accent TTS with browser TTS fallback
- Wake word: "Hey JARVIS" (always listening when active)
- 5 personality modes: default (British JARVIS), casual, formal, funny, pirate

Your 100+ Tools (USE THEM — this is what you can actually do):
- NOTES: Create, list, search, delete notes
- SYSTEM CONTROL: Open/kill apps, set volume/brightness, toggle WiFi/Bluetooth, lock PC, minimize all, take screenshots, type text, search images/videos, switch windows, snap/split screen, virtual desktops, task manager info, shutdown/restart/sleep timer, change wallpaper, internet speed test, battery saver, startup apps, night light
- PRODUCTIVITY: Calculator, timers, reminders, clipboard read/write, todo list, daily briefing
- WORKOUT COACH: Start/stop workout sessions, track sets and exercises, get coached through your routine. Say "start workout" to begin, "done" after each set, "skip" to skip exercise, "what's left" for status, "stop workout" to end early. Pre-loaded with your dumbbell routine.
- INFORMATION: Weather, news headlines, Wikipedia lookup, word definitions, currency conversion, cricket scores, stock prices
- MEDIA: Play/pause/skip music, open YouTube, screen recording, mute/unmute
- FILES: Find files, open files, move/copy/delete files, create folders, list running apps, check disk space, recycle bin info. Screenshot can save to Desktop, Documents, or any custom path.
- HABITAT CODE: Repo info, strategy advice, QA draft generation, earnings tracking, pre-submit checklist, task tracking, implicit requirement ideas, submission limits, open work sites, PR sweet spot scoring
- FILMMAKER: Movie lookup, find similar movies, film terminology, shot list generation, casting notes, location scouting, rehearsal mode (read dialogue), budget estimation, open IMDB
- SCREEN CONTROL (AI Vision): See what's on screen, click buttons/elements by description, read screen text, fill form fields by voice, scroll up/down, navigate app menus — all powered by screenshot + Claude Vision
- AUTOMATION CHAINS: Create named routines (morning routine, work mode, bedtime), run chains of tools with one command, list/delete chains
- PERSISTENT MEMORY: Remember facts across sessions, recall memories by topic, list all memories, forget specific items
- INTEGRATIONS: Open Gmail/compose/search emails, Google Calendar events, WhatsApp messages, Telegram, Notion
- ORB THEMES: iron_man (gold), matrix (green), ocean (blue), fire (red), minimal (white), cyberpunk (purple) — say "matrix theme" to switch

Personality:
- Speak like MCU JARVIS — refined British manner, witty but professional
- Keep it concise — you're spoken aloud, not a blog post
- Address Suchet as "sir" occasionally
- Be confident about your capabilities — you're a powerful AI assistant, act like it
- When you genuinely can't do something (no tool for it), say "I don't have that capability yet, sir" — not "that's beyond AI"

SPEECH RECOGNITION INTELLIGENCE:
- The user talks to you via VOICE. The transcript has speech recognition errors — words get misheard, dropped, or garbled.
- YOU must think like a human and understand INTENT, not exact words.
- "cloud" = Claude. "no pad" / "not pad" = Notepad. "screen shut" = screenshot. "blue to" = Bluetooth. "clothes notepad" = close Notepad.
- If a word seems wrong, figure out what they MEANT from context. You're smart — use that intelligence.
- NEVER say "I didn't understand" — always try your best to interpret and act.

CRITICAL TOOL USAGE RULES:
- ALWAYS call a tool when the user asks you to DO something (open, close, create, toggle, check, set, take, etc.)
- NEVER assume an app is already open/closed/enabled/disabled — always call the tool to actually do it
- NEVER say "it's already done" or "already enabled" without calling the tool first
- Every voice command is an ACTION REQUEST. Execute it immediately with the right tool. No questions, no assumptions.
- If user says "open notepad" → call open_app. "close notepad" → call kill_process. "enable bluetooth" → call toggle_bluetooth. EVERY SINGLE TIME.
- NEVER call the same tool twice for the same request. One tool call per action.
- NEVER promise to "work on something in the background" or "notify you when done." You respond to commands instantly. You do NOT work autonomously.
- NEVER say "Claude and I are working together" — YOU are the AI. Just do the task or say honestly what you can and cannot do.
- If someone asks you to "build" or "develop" something complex like a whole system, be honest: "That needs to be built in Claude Code, sir. I can help with planning, but the actual coding happens there."

Rules:
- Keep responses under 3 sentences for simple queries, up to 5 for complex topics
- Never use markdown formatting (this is spoken aloud)
- Use natural speech patterns, contractions
- For Habitat: prioritize implicit requirements strategy, never guess commit hashes
- For filmmaking: think like a creative director, suggest visual ideas, reference great films
- Always use your tools when relevant — don't just talk about what you could do, DO it
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


async def chat_stream(
    messages: list[dict[str, str]],
    tools: list[dict[str, Any]] | None = None,
    extra_system: str = "",
) -> AsyncGenerator[dict[str, Any], None]:
    """Stream chat response. Yields text chunks, then a final 'done' with tool_calls."""
    last_msg = messages[-1]["content"] if messages else ""
    user_text = last_msg if isinstance(last_msg, str) else ""

    # Non-streaming fallback for non-Claude backends or simple queries
    if _backend != "claude" or not _claude_client:
        result = await chat(messages, tools, extra_system)
        yield {"type": "full", "text": result.get("text", ""), "tool_calls": result.get("tool_calls", [])}
        return

    # Simple queries → Ollama (free, non-streaming)
    if _is_simple_query(user_text):
        try:
            result = await _chat_ollama(messages, None, extra_system)
            yield {"type": "full", "text": result.get("text", ""), "tool_calls": []}
            return
        except Exception:
            pass  # Fall through to Claude streaming

    # Cache check
    cached = _check_cache(user_text)
    if cached and not tools:
        yield {"type": "full", "text": cached, "tool_calls": []}
        return

    system = SYSTEM_PROMPT + ("\n\n" + extra_system if extra_system else "")
    kwargs: dict[str, Any] = {
        "model": CLAUDE_MODEL,
        "max_tokens": 500,
        "system": system,
        "messages": messages,
    }
    if tools:
        kwargs["tools"] = tools

    try:
        async with _claude_client.messages.stream(**kwargs) as stream:
            async for text in stream.text_stream:
                yield {"type": "chunk", "text": text}

            response = await stream.get_final_message()

        # Extract full text and tool calls from final message
        full_text = ""
        tool_calls: list[dict[str, Any]] = []
        for block in response.content:
            if block.type == "text":
                full_text = block.text
            elif block.type == "tool_use":
                tool_calls.append({"id": block.id, "name": block.name, "input": block.input})

        _save_cache(user_text, full_text)
        yield {"type": "done", "text": full_text, "tool_calls": tool_calls}

    except Exception as e:
        log.exception("Streaming error, falling back to non-streaming")
        try:
            result = await chat(messages, tools, extra_system)
            yield {"type": "full", "text": result.get("text", ""), "tool_calls": result.get("tool_calls", [])}
        except Exception:
            yield {"type": "full", "text": f"I'm having trouble right now, sir. Error: {e}", "tool_calls": []}


async def vision_analyze(image_path: str, prompt: str) -> str:
    """Analyze a screenshot with Claude Vision. Returns clean human answer."""
    if not _claude_client:
        return "Vision not available — no Claude API key."

    img_bytes = Path(image_path).read_bytes()
    img_b64 = base64.b64encode(img_bytes).decode()

    ext = Path(image_path).suffix.lower()
    media_type = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "bmp": "image/bmp"}.get(ext.lstrip("."), "image/png")

    system = """You are JARVIS's eyes. You analyze screenshots to help the user.
Rules:
- Give SHORT, CLEAN, HUMAN answers — like talking to a friend, not writing a report.
- NEVER use markdown formatting (no **, no ##, no bullets). Just plain sentences.
- If the user asks about something specific (order number, text, button), answer THAT directly.
- Read ALL visible text carefully. Order numbers, names, dates, prices — report them exactly.
- Don't describe the UI layout unless asked. Focus on the CONTENT the user cares about."""

    try:
        response = await _claude_client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=500,
            system=system,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": img_b64}},
                    {"type": "text", "text": prompt},
                ],
            }],
        )
        return response.content[0].text
    except Exception as e:
        log.exception("Vision analysis error")
        return f"Vision error: {e}"


async def vision_find_element(image_path: str, element_description: str) -> dict[str, Any]:
    """Find a UI element on screen and return its coordinates.
    Uses fractional positioning (0.0-1.0) for much better accuracy.
    Returns: {"found": bool, "x": int, "y": int, "description": str}
    """
    if not _claude_client:
        return {"found": False, "x": 0, "y": 0, "description": "Vision not available"}

    img_bytes = Path(image_path).read_bytes()
    img_b64 = base64.b64encode(img_bytes).decode()

    # Get screen size for converting fractions to pixels
    try:
        import subprocess
        r = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command",
             "[System.Windows.Forms.Screen]::PrimaryScreen.Bounds | Select-Object Width,Height | ConvertTo-Json"],
            capture_output=True, text=True, timeout=5
        )
        screen = json.loads(r.stdout)
        screen_w, screen_h = screen["Width"], screen["Height"]
    except Exception:
        screen_w, screen_h = 1920, 1080

    prompt = f"""Look at this screenshot ({screen_w}x{screen_h} pixels). Find the UI element: "{element_description}"

IMPORTANT:
- IGNORE the browser bookmark bar. Focus on the actual page content.
- IGNORE browser chrome (tabs, address bar) unless specifically asked.
- Look for the element in the MAIN CONTENT area of the page/app.

Return ONLY a JSON object:
{{"found": true/false, "fx": 0.0-1.0, "fy": 0.0-1.0, "description": "what you found"}}

Where fx = horizontal position (0.0=left edge, 0.5=center, 1.0=right edge)
And fy = vertical position (0.0=top edge, 0.5=center, 1.0=bottom edge)

Raw JSON only. No markdown. No code blocks."""

    try:
        response = await _claude_client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=200,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": img_b64}},
                    {"type": "text", "text": prompt},
                ],
            }],
        )
        text = response.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("```")[1].strip()
            if text.startswith("json"):
                text = text[4:].strip()
        result = json.loads(text)

        # Convert fractions to pixels
        if result.get("found"):
            fx = float(result.get("fx", 0.5))
            fy = float(result.get("fy", 0.5))
            result["x"] = int(fx * screen_w)
            result["y"] = int(fy * screen_h)

        return result
    except Exception as e:
        log.exception("Vision find element error")
        return {"found": False, "x": 0, "y": 0, "description": f"Error: {e}"}
