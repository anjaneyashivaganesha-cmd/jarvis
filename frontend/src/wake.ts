/**
 * Wake word detector — listens for "Hey JARVIS" / "JARVIS" continuously.
 * Uses the same Web Speech API but in a separate always-on recognition instance.
 */

type WakeCallback = () => void;

const SpeechRecognition =
  (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;

export class WakeWordDetector {
  private recognition: any | null = null;
  private active = false;
  private onWake: WakeCallback;
  private wakeWords = ["jarvis", "hey jarvis", "ok jarvis", "yo jarvis"];

  constructor(onWake: WakeCallback) {
    this.onWake = onWake;

    if (!SpeechRecognition) {
      console.warn("[wake] Speech recognition not supported");
      return;
    }

    this.recognition = new SpeechRecognition();
    this.recognition.continuous = true;
    this.recognition.interimResults = true;
    this.recognition.lang = "en-US";

    this.recognition.onresult = (event: any) => {
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const transcript = event.results[i][0].transcript.toLowerCase().trim();
        if (this.wakeWords.some((w) => transcript.includes(w))) {
          console.log("[wake] Wake word detected:", transcript);
          this.onWake();
        }
      }
    };

    this.recognition.onerror = (event: any) => {
      if (event.error !== "no-speech" && event.error !== "aborted") {
        console.error("[wake] error:", event.error);
      }
    };

    this.recognition.onend = () => {
      if (this.active) {
        // Auto-restart
        setTimeout(() => {
          try { this.recognition.start(); } catch (_) {}
        }, 200);
      }
    };
  }

  start(): void {
    if (!this.recognition || this.active) return;
    this.active = true;
    try {
      this.recognition.start();
      console.log("[wake] Listening for wake word...");
    } catch (_) {}
  }

  stop(): void {
    this.active = false;
    if (this.recognition) {
      try { this.recognition.stop(); } catch (_) {}
    }
  }

  isActive(): boolean {
    return this.active;
  }
}
