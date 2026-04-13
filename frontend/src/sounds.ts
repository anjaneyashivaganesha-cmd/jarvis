/**
 * Sound effects for JARVIS using Web Audio API oscillators.
 * No external files needed — generates tones programmatically.
 */

export class SoundEffects {
  private ctx: AudioContext | null = null;

  private getCtx(): AudioContext {
    if (!this.ctx) this.ctx = new AudioContext();
    return this.ctx;
  }

  private playTone(freq: number, duration: number, type: OscillatorType = "sine", vol = 0.15): void {
    const ctx = this.getCtx();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = type;
    osc.frequency.value = freq;
    gain.gain.value = vol;
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + duration);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + duration);
  }

  /** Startup chime — two ascending tones */
  startup(): void {
    this.playTone(440, 0.15);
    setTimeout(() => this.playTone(660, 0.2), 150);
  }

  /** Mic activated — short blip */
  micOn(): void {
    this.playTone(880, 0.08, "sine", 0.1);
  }

  /** Mic deactivated — descending blip */
  micOff(): void {
    this.playTone(440, 0.08, "sine", 0.1);
  }

  /** Thinking — subtle tick */
  thinking(): void {
    this.playTone(600, 0.05, "triangle", 0.08);
  }

  /** Response received — gentle chime */
  response(): void {
    this.playTone(523, 0.1, "sine", 0.1);
    setTimeout(() => this.playTone(659, 0.15, "sine", 0.1), 100);
  }

  /** Error — low buzz */
  error(): void {
    this.playTone(220, 0.2, "sawtooth", 0.08);
  }

  /** Connected — warm chord */
  connected(): void {
    this.playTone(330, 0.2, "sine", 0.08);
    setTimeout(() => this.playTone(415, 0.2, "sine", 0.08), 100);
    setTimeout(() => this.playTone(523, 0.3, "sine", 0.08), 200);
  }
}
