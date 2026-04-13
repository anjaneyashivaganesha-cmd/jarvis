/**
 * Browser-based TTS using Web Speech Synthesis API.
 * Free, no API key needed. Falls back gracefully.
 */

export class BrowserTTS {
  private synth: SpeechSynthesis;
  private voice: SpeechSynthesisVoice | null = null;
  private onStartCb: (() => void) | null = null;
  private onEndCb: (() => void) | null = null;

  constructor() {
    this.synth = window.speechSynthesis;
    this.loadVoice();

    // Voices may load async
    if (speechSynthesis.onvoiceschanged !== undefined) {
      speechSynthesis.onvoiceschanged = () => this.loadVoice();
    }
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

  speak(text: string): void {
    // Cancel any ongoing speech
    this.synth.cancel();

    const utterance = new SpeechSynthesisUtterance(text);

    if (this.voice) {
      utterance.voice = this.voice;
    }

    utterance.rate = 1.0;
    utterance.pitch = 0.9;
    utterance.volume = 1.0;

    utterance.onstart = () => {
      this.onStartCb?.();
    };

    utterance.onend = () => {
      this.onEndCb?.();
    };

    utterance.onerror = (e) => {
      console.error("[tts] error:", e);
      this.onEndCb?.();
    };

    this.synth.speak(utterance);
  }

  stop(): void {
    this.synth.cancel();
  }
}
