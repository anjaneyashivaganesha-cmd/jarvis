export class AudioPlayer {
  private context: AudioContext | null = null;

  private getContext(): AudioContext {
    if (!this.context) {
      this.context = new AudioContext();
    }
    return this.context;
  }

  async playBase64(base64Audio: string, format = "audio/mpeg"): Promise<void> {
    const ctx = this.getContext();
    const binary = atob(base64Audio);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) {
      bytes[i] = binary.charCodeAt(i);
    }

    const audioBuffer = await ctx.decodeAudioData(bytes.buffer);
    const source = ctx.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(ctx.destination);
    source.start(0);
  }

  getAnalyser(): AnalyserNode | null {
    if (!this.context) return null;
    const analyser = this.context.createAnalyser();
    analyser.fftSize = 256;
    return analyser;
  }
}
