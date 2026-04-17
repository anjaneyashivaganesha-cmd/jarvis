"""JARVIS Native Service — Runs outside browser, always listening.

This script runs as a background process at Windows startup (before login).
It listens for the wake word "JARVIS" using the microphone directly.
When detected, it verifies the speaker's voice and can:
- Unlock the PC
- Launch JARVIS browser app
- Execute basic commands

Usage:
  python jarvis_service.py              # Run normally
  python jarvis_service.py --unlock PIN # Enable auto-unlock with PIN
"""

from __future__ import annotations

import ctypes
import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

import speech_recognition as sr

# Add app to path for voice_auth
sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(
    level=logging.INFO,
    format="[JARVIS Service] %(asctime)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("jarvis_service")

# --- Config ---
WAKE_WORDS = ["jarvis", "hey jarvis", "ok jarvis", "wake up jarvis", "wake up"]
JARVIS_BAT = Path(__file__).parent.parent / "start-jarvis.bat"
VOICEPRINT_FILE = Path(__file__).parent / "db" / "voiceprint.json"
SERVICE_CONFIG = Path(__file__).parent / "db" / "service_config.json"


def _load_pin() -> str:
    """Load unlock PIN from secure config file."""
    if SERVICE_CONFIG.exists():
        try:
            data = json.loads(SERVICE_CONFIG.read_text())
            return data.get("unlock_pin", "")
        except Exception:
            pass
    return ""

# Voice auth
_voiceprint_loaded = False


def check_voiceprint() -> bool:
    """Check if a voiceprint is enrolled."""
    return VOICEPRINT_FILE.exists()


def is_jarvis_running() -> bool:
    """Check if JARVIS backend is already running."""
    try:
        import httpx
        r = httpx.get("http://localhost:8000/health", timeout=2)
        return r.status_code == 200
    except Exception:
        return False


def launch_jarvis():
    """Launch the full JARVIS system (backend + frontend + browser)."""
    log.info("Launching JARVIS...")
    subprocess.Popen(
        ["cmd", "/c", str(JARVIS_BAT)],
        creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def unlock_screen(pin: str = ""):
    """Unlock the Windows lock screen."""
    user32 = ctypes.windll.user32

    # Press any key to dismiss the lock screen overlay
    # Then type PIN if provided
    log.info("Attempting to unlock screen...")

    # Press Escape to dismiss notifications, then Enter or type PIN
    user32.keybd_event(0x1B, 0, 0, 0)  # Escape down
    user32.keybd_event(0x1B, 0, 2, 0)  # Escape up
    time.sleep(0.5)

    # Press Space to go to password/PIN entry
    user32.keybd_event(0x20, 0, 0, 0)  # Space down
    user32.keybd_event(0x20, 0, 2, 0)  # Space up
    time.sleep(1)

    if pin:
        # Type PIN digit by digit
        vk_map = {
            "0": 0x30, "1": 0x31, "2": 0x32, "3": 0x33, "4": 0x34,
            "5": 0x35, "6": 0x36, "7": 0x37, "8": 0x38, "9": 0x39,
        }
        for char in pin:
            if char in vk_map:
                vk = vk_map[char]
                user32.keybd_event(vk, 0, 0, 0)
                user32.keybd_event(vk, 0, 2, 0)
                time.sleep(0.1)

        # Press Enter to submit PIN
        time.sleep(0.3)
        user32.keybd_event(0x0D, 0, 0, 0)  # Enter
        user32.keybd_event(0x0D, 0, 2, 0)
        log.info("PIN entered, screen should be unlocking...")
    else:
        # Just press Enter (for no-password setups)
        user32.keybd_event(0x0D, 0, 0, 0)
        user32.keybd_event(0x0D, 0, 2, 0)
        log.info("Enter pressed on lock screen")


def speak(text: str):
    """Speak using Windows SAPI (works even without browser)."""
    try:
        subprocess.Popen(
            ["powershell.exe", "-NoProfile", "-Command",
             f"Add-Type -AssemblyName System.Speech; "
             f"$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
             f"$s.Speak('{text}')"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass


def listen_loop(unlock_pin: str = ""):
    """Main loop — listens for Ctrl+Alt+J hotkey to activate JARVIS.

    Your laptop's Intel Smart Sound mic needs Chrome's audio processing
    for clear voice capture. So the native service uses a hotkey instead:

    - Press Ctrl+Alt+J on lock screen → unlocks with PIN
    - Press Ctrl+Alt+J on desktop → launches JARVIS if not running
    """
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32

    # Register hotkey: Ctrl+Alt+J (ID=1)
    MOD_CTRL = 0x0002
    MOD_ALT = 0x0001
    VK_J = 0x4A
    HOTKEY_ID = 1

    if not user32.RegisterHotKey(None, HOTKEY_ID, MOD_CTRL | MOD_ALT, VK_J):
        log.error("Could not register hotkey Ctrl+Alt+J")
        return

    log.info("Hotkey registered: Ctrl+Alt+J")
    log.info("Press Ctrl+Alt+J on lock screen to unlock, or on desktop to launch JARVIS")
    speak("JARVIS service is online. Press Control Alt J to activate.")

    msg = wintypes.MSG()
    while True:
        try:
            # Wait for hotkey message
            if user32.GetMessageW(ctypes.byref(msg), None, 0, 0):
                if msg.message == 0x0312:  # WM_HOTKEY
                    log.info("Hotkey pressed! Activating JARVIS...")
                    speak("Yes sir.")

                    if unlock_pin:
                        # Check if screen might be locked
                        fg = user32.GetForegroundWindow()
                        if fg == 0:
                            # Likely locked
                            speak("Unlocking, sir.")
                            unlock_screen(unlock_pin)
                            time.sleep(3)

                    if not is_jarvis_running():
                        speak("Launching JARVIS.")
                        launch_jarvis()
                    else:
                        speak("JARVIS is ready, sir.")

        except KeyboardInterrupt:
            log.info("Service stopped")
            break
        except Exception as e:
            log.error("Error: %s", e)
            time.sleep(1)

    user32.UnregisterHotKey(None, HOTKEY_ID)


def main():
    """Entry point."""
    pin = _load_pin()

    log.info("=" * 50)
    log.info("JARVIS Native Service starting...")
    log.info("Wake words: %s", ", ".join(WAKE_WORDS))
    log.info("Voiceprint enrolled: %s", check_voiceprint())
    log.info("Auto-unlock: %s", "enabled" if pin else "disabled")
    log.info("=" * 50)

    listen_loop(unlock_pin=pin)


if __name__ == "__main__":
    main()
