"""Voice authentication for JARVIS — only responds to the enrolled user's voice.

Uses MFCC (Mel-Frequency Cepstral Coefficients) for voice fingerprinting.
Enrollment: Record 5 seconds of speech, extract MFCC features, save as voiceprint.
Verification: Compare incoming audio MFCCs against stored voiceprint using cosine similarity.
"""

from __future__ import annotations

import base64
import io
import json
import logging
from pathlib import Path
from typing import Any

import numpy as np
from scipy.fft import dct
from scipy.io import wavfile

log = logging.getLogger("jarvis.voice_auth")

# Store voiceprint here
_VOICEPRINT_FILE = Path(__file__).parent.parent / "db" / "voiceprint.json"
_voiceprint: np.ndarray | None = None
_auth_enabled = False
_SIMILARITY_THRESHOLD = 0.75  # 0.0 = no match, 1.0 = perfect match


def _extract_mfcc(audio_data: np.ndarray, sample_rate: int, n_mfcc: int = 13) -> np.ndarray:
    """Extract MFCC features from audio — pure numpy/scipy, no external libs."""
    # Pre-emphasis filter
    emphasized = np.append(audio_data[0], audio_data[1:] - 0.97 * audio_data[:-1])

    # Frame the signal (25ms frames, 10ms step)
    frame_size = int(0.025 * sample_rate)
    frame_step = int(0.010 * sample_rate)
    num_frames = max(1, int(np.ceil((len(emphasized) - frame_size) / frame_step)))

    # Pad signal
    pad_length = num_frames * frame_step + frame_size
    padded = np.zeros(pad_length)
    padded[:len(emphasized)] = emphasized

    # Create frames
    indices = np.tile(np.arange(0, frame_size), (num_frames, 1)) + \
              np.tile(np.arange(0, num_frames * frame_step, frame_step), (frame_size, 1)).T
    frames = padded[indices.astype(np.int32)]

    # Apply Hamming window
    frames *= np.hamming(frame_size)

    # FFT and power spectrum
    nfft = 512
    mag_frames = np.absolute(np.fft.rfft(frames, nfft))
    pow_frames = (1.0 / nfft) * (mag_frames ** 2)

    # Mel filterbank
    n_filters = 26
    low_freq_mel = 0
    high_freq_mel = 2595 * np.log10(1 + (sample_rate / 2) / 700)
    mel_points = np.linspace(low_freq_mel, high_freq_mel, n_filters + 2)
    hz_points = 700 * (10 ** (mel_points / 2595) - 1)
    bin_points = np.floor((nfft + 1) * hz_points / sample_rate).astype(int)

    fbank = np.zeros((n_filters, int(np.floor(nfft / 2 + 1))))
    for m in range(1, n_filters + 1):
        f_m_minus = bin_points[m - 1]
        f_m = bin_points[m]
        f_m_plus = bin_points[m + 1]

        for k in range(f_m_minus, f_m):
            if f_m != f_m_minus:
                fbank[m - 1, k] = (k - f_m_minus) / (f_m - f_m_minus)
        for k in range(f_m, f_m_plus):
            if f_m_plus != f_m:
                fbank[m - 1, k] = (f_m_plus - k) / (f_m_plus - f_m)

    filter_banks = np.dot(pow_frames, fbank.T)
    filter_banks = np.where(filter_banks == 0, np.finfo(float).eps, filter_banks)
    filter_banks = 20 * np.log10(filter_banks)

    # DCT to get MFCCs
    mfcc = dct(filter_banks, type=2, axis=1, norm='ortho')[:, :n_mfcc]

    # Mean normalize
    mfcc -= np.mean(mfcc, axis=0)

    return mfcc


def _audio_from_base64_wav(b64_audio: str) -> tuple[np.ndarray, int]:
    """Decode base64 WAV audio to numpy array."""
    audio_bytes = base64.b64decode(b64_audio)
    buf = io.BytesIO(audio_bytes)
    sample_rate, data = wavfile.read(buf)

    # Convert to float
    if data.dtype == np.int16:
        data = data.astype(np.float32) / 32768.0
    elif data.dtype == np.int32:
        data = data.astype(np.float32) / 2147483648.0
    elif data.dtype == np.uint8:
        data = (data.astype(np.float32) - 128) / 128.0

    # Convert stereo to mono
    if len(data.shape) > 1:
        data = np.mean(data, axis=1)

    return data, sample_rate


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two MFCC feature vectors."""
    # Average MFCCs across time to get a single vector per recording
    vec_a = np.mean(a, axis=0)
    vec_b = np.mean(b, axis=0)

    dot = np.dot(vec_a, vec_b)
    norm = np.linalg.norm(vec_a) * np.linalg.norm(vec_b)
    if norm == 0:
        return 0.0
    return float(dot / norm)


def enroll_voice(b64_audio: str) -> dict[str, Any]:
    """Enroll the user's voice. Call with 5+ seconds of speech audio (WAV base64)."""
    global _voiceprint, _auth_enabled
    try:
        data, sr = _audio_from_base64_wav(b64_audio)

        if len(data) < sr * 2:
            return {"success": False, "error": "Audio too short. Need at least 2 seconds of speech."}

        mfcc = _extract_mfcc(data, sr)
        _voiceprint = mfcc

        # Save to disk
        _VOICEPRINT_FILE.parent.mkdir(parents=True, exist_ok=True)
        voiceprint_data = {
            "mfcc_mean": np.mean(mfcc, axis=0).tolist(),
            "mfcc_std": np.std(mfcc, axis=0).tolist(),
            "sample_rate": sr,
            "enrolled": True,
        }
        _VOICEPRINT_FILE.write_text(json.dumps(voiceprint_data))
        _auth_enabled = True

        log.info("Voice enrolled successfully")
        return {"success": True, "message": "Voice enrolled. JARVIS will now only respond to your voice."}

    except Exception as e:
        log.exception("Voice enrollment error")
        return {"success": False, "error": str(e)}


def verify_voice(b64_audio: str) -> dict[str, Any]:
    """Verify if the speaker matches the enrolled voice."""
    global _voiceprint
    if not _auth_enabled or _voiceprint is None:
        return {"verified": True, "score": 1.0, "reason": "Voice auth not enabled"}

    try:
        data, sr = _audio_from_base64_wav(b64_audio)

        if len(data) < sr * 0.5:
            return {"verified": False, "score": 0.0, "reason": "Audio too short to verify"}

        mfcc = _extract_mfcc(data, sr)
        score = _cosine_similarity(mfcc, _voiceprint)

        verified = score >= _SIMILARITY_THRESHOLD
        log.info("Voice verification: score=%.3f threshold=%.3f verified=%s", score, _SIMILARITY_THRESHOLD, verified)

        return {
            "verified": verified,
            "score": round(score, 3),
            "reason": "Voice match" if verified else "Voice does not match the enrolled user",
        }

    except Exception as e:
        log.exception("Voice verification error")
        return {"verified": False, "score": 0.0, "reason": str(e)}


def load_voiceprint() -> bool:
    """Load saved voiceprint from disk on startup."""
    global _voiceprint, _auth_enabled
    if _VOICEPRINT_FILE.exists():
        try:
            data = json.loads(_VOICEPRINT_FILE.read_text())
            if data.get("enrolled"):
                _voiceprint = np.array([data["mfcc_mean"]])  # Use mean as reference
                _auth_enabled = True
                log.info("Voiceprint loaded from disk")
                return True
        except Exception:
            log.exception("Failed to load voiceprint")
    return False


def is_auth_enabled() -> bool:
    return _auth_enabled


def disable_auth():
    """Disable voice authentication."""
    global _auth_enabled
    _auth_enabled = False
    if _VOICEPRINT_FILE.exists():
        _VOICEPRINT_FILE.unlink()
    log.info("Voice auth disabled")
