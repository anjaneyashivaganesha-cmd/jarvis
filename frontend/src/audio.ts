export class AudioPlayer {
  private context: AudioContext | null = null;
  private currentSource: AudioBufferSourceNode | null = null;
  private _onEndCallback: (() => void) | null = null;

  private getContext(): AudioContext {
    if (!this.context) {
      this.context = new AudioContext();
    }
    return this.context;
  }

  onEnd(cb: () => void): void {
    this._onEndCallback = cb;
  }

  async playBase64(base64Audio: string): Promise<void> {
    const ctx = this.getContext();
    const binary = atob(base64Audio);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) {
      bytes[i] = binary.charCodeAt(i);
    }

    const audioBuffer = await ctx.decodeAudioData(bytes.buffer.slice(0));
    const source = ctx.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(ctx.destination);
    this.currentSource = source;

    return new Promise<void>((resolve) => {
      source.onended = () => {
        this.currentSource = null;
        this._onEndCallback?.();
        resolve();
      };
      source.start(0);
    });
  }

  stop(): void {
    if (this.currentSource) {
      try {
        this.currentSource.onended = null; // prevent double-fire
        this.currentSource.stop();
      } catch (_) {}
      this.currentSource = null;
      this._onEndCallback?.();
    }
  }

  isPlaying(): boolean {
    return this.currentSource !== null;
  }

  getAnalyser(): AnalyserNode | null {
    if (!this.context) return null;
    const analyser = this.context.createAnalyser();
    analyser.fftSize = 256;
    return analyser;
  }
}
