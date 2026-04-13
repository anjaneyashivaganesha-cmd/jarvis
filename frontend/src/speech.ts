type TranscriptCallback = (text: string, isFinal: boolean) => void;

const SpeechRecognition =
  (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;

export class SpeechInput {
  private recognition: any | null = null;
  private listening = false;
  private onTranscript: TranscriptCallback;

  constructor(onTranscript: TranscriptCallback) {
    this.onTranscript = onTranscript;

    if (!SpeechRecognition) {
      console.error("Web Speech API not supported in this browser");
      return;
    }

    this.recognition = new SpeechRecognition();
    this.recognition.continuous = true;
    this.recognition.interimResults = true;
    this.recognition.lang = "en-US";

    this.recognition.onresult = (event: any) => {
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i];
        this.onTranscript(result[0].transcript, result.isFinal);
      }
    };

    this.recognition.onerror = (event: any) => {
      console.error("[speech] error:", event.error);
      if (event.error !== "no-speech") {
        this.listening = false;
      }
    };

    this.recognition.onend = () => {
      // Auto-restart if still supposed to be listening
      if (this.listening) {
        this.recognition.start();
      }
    };
  }

  toggle(): boolean {
    if (!this.recognition) return false;

    if (this.listening) {
      this.listening = false;
      this.recognition.stop();
    } else {
      this.listening = true;
      this.recognition.start();
    }
    return this.listening;
  }

  isListening(): boolean {
    return this.listening;
  }
}
