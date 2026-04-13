"""Claude Haiku client for JARVIS."""

from __future__ import annotations

import logging
from typing import Any

from anthropic import AsyncAnthropic

from app.config import ANTHROPIC_API_KEY, CLAUDE_MODEL

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

client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None


async def chat(
    messages: list[dict[str, str]],
    tools: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Send messages to Claude Haiku and get a response.

    Returns dict with 'text' and optionally 'tool_calls'.
    """
    if not client:
        return {"text": "API key not configured. Please add ANTHROPIC_API_KEY to backend/.env"}

    kwargs: dict[str, Any] = {
        "model": CLAUDE_MODEL,
        "max_tokens": 300,
        "system": SYSTEM_PROMPT,
        "messages": messages,
    }

    if tools:
        kwargs["tools"] = tools

    try:
        response = await client.messages.create(**kwargs)
    except Exception as e:
        log.exception("Claude API error")
        return {"text": f"I'm having trouble thinking right now. Error: {e}"}

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
