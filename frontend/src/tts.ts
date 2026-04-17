/**
 * Browser-based TTS using Web Speech Synthesis API.
 * Free, no API key needed. Falls back gracefully.
 */

export class BrowserTTS {
  private synth: SpeechSynthesis;
  private voice: SpeechSynthesisVoice | null = null;
  private onStartCb: (() => void) | null = null;
  private onEndCb: (() => void) | null = null;
  private safetyTimeout: number | null = null;
  private isSpeaking = false;

  constructor() {
    this.synth = window.speechSynthesis;
    this.loadVoice();

    // Voices may load async
    if (speechSynthesis.onvoiceschanged !== undefined) {
      speechSynthesis.onvoiceschanged = () => this.loadVoice();
    }

    // Chrome bug workaround: speechSynthesis.speaking can get stuck.
    // Periodically check and unstick it.
    setInterval(() => {
      if (this.isSpeaking && !this.synth.speaking && !this.synth.pending) {
        console.warn("[tts] Chrome stuck — synth reports not speaking but we never got onend");
        this.forceEnd();
      }
    }, 3000);
  }

  private loadVoice(): void {
    const voices = this.synth.getVoices();

    // Prefer British English male voice (JARVIS style)
    const preferred = [
      "Google UK English Male",
      "Microsoft Ryan",
      "Microsoft George",
      "Daniel",
      "Google UK English Female",
      "Microsoft Hazel",
    ];

    for (const name of preferred) {
      const found = voices.find((v) => v.name.includes(name));
      if (found) {
        this.voice = found;
        console.log("[tts] Using voice:", found.name);
        return;
      }
    }

    // Fallback: any English voice
    const english = voices.find((v) => v.lang.startsWith("en"));
    if (english) {
      this.voice = english;
      console.log("[tts] Fallback voice:", english.name);
    }
  }

  onStart(cb: () => void): void {
    this.onStartCb = cb;
  }

  onEnd(cb: () => void): void {
    this.onEndCb = cb;
  }

  private forceEnd(): void {
    this.isSpeaking = false;
    if (this.safetyTimeout) {
      clearTimeout(this.safetyTimeout);
      this.safetyTimeout = null;
    }
    this.onEndCb?.();
  }

  speak(text: string): void {
    // Cancel any ongoing speech
    this.synth.cancel();
    this.isSpeaking = false;
    if (this.safetyTimeout) {
      clearTimeout(this.safetyTimeout);
      this.safetyTimeout = null;
    }

    // Small delay after cancel to avoid Chrome race condition
    setTimeout(() => {
      const utterance = new SpeechSynthesisUtterance(text);

      if (this.voice) {
        utterance.voice = this.voice;
      }

      utterance.rate = 1.0;
      utterance.pitch = 0.9;
      utterance.volume = 1.0;

      utterance.onstart = () => {
        this.isSpeaking = true;
        this.onStartCb?.();
      };

      utterance.onend = () => {
        this.isSpeaking = false;
        if (this.safetyTimeout) {
          clearTimeout(this.safetyTimeout);
          this.safetyTimeout = null;
        }
        this.onEndCb?.();
      };

      utterance.onerror = (e) => {
        console.error("[tts] error:", e);
        this.forceEnd();
      };

      this.synth.speak(utterance);

      // Safety timeout: if speech doesn't finish in 25s, force end
      // Handles Chrome's bug where onend never fires for long utterances
      this.safetyTimeout = window.setTimeout(() => {
        if (this.isSpeaking) {
          console.warn("[tts] Safety timeout — forcing speech end");
          this.synth.cancel();
          this.forceEnd();
        }
      }, 25000);
    }, 50);
  }

  stop(): void {
    this.synth.cancel();
    if (this.isSpeaking) {
      this.forceEnd();
    }
  }
}
