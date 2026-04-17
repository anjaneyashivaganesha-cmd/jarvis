"""Whisper Speech-to-Text for JARVIS — accurate transcription for all accents.

Replaces browser's Web Speech API with OpenAI's Whisper (runs locally, free).
First call downloads the model (~150MB for 'base'), subsequent calls are instant.
"""

from __future__ import annotations

import base64
import io
import logging
import tempfile
from pathlib import Path

log = logging.getLogger("jarvis.whisper")

_model = None
_model_loading = False


def _get_model():
    """Lazy-load Whisper model on first use."""
    global _model, _model_loading
    if _model is not None:
        return _model
    if _model_loading:
        return None

    _model_loading = True
    try:
        from faster_whisper import WhisperModel
        log.info("Loading Whisper model (base)... First time takes ~30s to download")
        # 'base' is good balance of speed and accuracy
        # 'small' is more accurate but slower
        _model = WhisperModel("base", device="cpu", compute_type="int8")
        log.info("Whisper model loaded!")
        _model_loading = False
        return _model
    except Exception as e:
        log.exception("Failed to load Whisper model")
        _model_loading = False
        return None


def transcribe_audio(audio_b64: str) -> str:
    """Transcribe base64 WAV audio using Whisper. Returns text."""
    model = _get_model()
    if not model:
        return ""

    try:
        # Decode base64 to bytes
        audio_bytes = base64.b64decode(audio_b64)

        # Save to temp file (Whisper needs a file path)
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp.write(audio_bytes)
        tmp.close()

        # Transcribe
        segments, info = model.transcribe(
            tmp.name,
            language="en",
            beam_size=5,
            vad_filter=True,  # Filter out silence
        )

        text = " ".join(seg.text.strip() for seg in segments).strip()

        # Clean up
        Path(tmp.name).unlink(missing_ok=True)

        log.info("Whisper transcription: %s", text[:100])
        return text

    except Exception as e:
        log.exception("Whisper transcription error")
        return ""


def preload_model():
    """Pre-load model in background to avoid delay on first command."""
    import threading
    threading.Thread(target=_get_model, daemon=True).start()
