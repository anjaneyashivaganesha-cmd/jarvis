"""ElevenLabs TTS client for JARVIS."""

from __future__ import annotations

import base64
import logging

import httpx

from app.config import ELEVENLABS_API_KEY, ELEVENLABS_VOICE_ID

log = logging.getLogger("jarvis.tts")

ELEVENLABS_URL = "https://api.elevenlabs.io/v1/text-to-speech"


async def synthesize(text: str) -> str | None:
    """Convert text to speech via ElevenLabs.

    Returns base64-encoded mp3 audio, or None if TTS is unavailable.
    """
    if not ELEVENLABS_API_KEY:
        log.warning("ElevenLabs API key not set — skipping TTS")
        return None

    url = f"{ELEVENLABS_URL}/{ELEVENLABS_VOICE_ID}?output_format=mp3_44100_128"

    headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
        "Content-Type": "application/json",
    }

    payload = {
        "text": text,
        "model_id": "eleven_turbo_v2_5",
        "voice_settings": {
            "stability": 0.4,
            "similarity_boost": 0.8,
            "style": 0.15,
            "use_speaker_boost": True,
        },
        "speed": 2.0,
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as http:
            resp = await http.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            audio_bytes = resp.content
            return base64.b64encode(audio_bytes).decode("ascii")
    except Exception:
        log.exception("ElevenLabs TTS error")
        return None
