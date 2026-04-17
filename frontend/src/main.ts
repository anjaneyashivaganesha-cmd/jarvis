import { JarvisSocket } from "./websocket";
import { AudioPlayer } from "./audio";
import { BrowserTTS } from "./tts";
import { ParticleOrb } from "./orb";
import { SoundEffects } from "./sounds";
import { addMessage, setStatus, startStreamingMessage, appendStreamChunk, endStreamingMessage } from "./ui";

// --- Core modules ---
const orbContainer = document.getElementById("orb-container")!;
const orb = new ParticleOrb(orbContainer);
const player = new AudioPlayer();
const sfx = new SoundEffects();
const tts = new BrowserTTS();
const micBtn = document.getElementById("mic-btn")!;
const stopBtn = document.getElementById("stop-btn")!;
const socket = new JarvisSocket();

// --- State machine ---
type JarvisState = "locked" | "idle" | "listening" | "thinking" | "speaking";
let state: JarvisState = "locked";
let lastSpeakTime = 0;
let thinkingTimeout: number | null = null;
let speakingTimeout: number | null = null;
let stateEnteredAt = 0; // timestamp when current state was entered

// Recognition reliability tracking
let recognitionFailCount = 0;
let lastRecognitionResult = Date.now();
let micBlocked = false;
let lastStartAttempt = 0;

const WAKE_WORDS = ["jarvis", "hey jarvis", "ok jarvis", "yo jarvis", "hi jarvis", "hello jarvis"];
const STOP_WORDS = ["stop", "stop jarvis", "shut up", "quiet", "enough", "stop talking",
  "ok stop", "jarvis stop", "hey jarvis stop", "wait", "jarvis wait",
  "hey jarvis wait", "hold on", "pause"];

// Fix common speech recognition mishearings — especially Indian English accent
const WORD_CORRECTIONS: Record<string, string> = {
  // JARVIS
  "service": "JARVIS", "jarvas": "JARVIS", "jervis": "JARVIS",
  "javas": "JARVIS", "jarves": "JARVIS", "nervous": "JARVIS",
  "java's": "JARVIS", "jarvis's": "JARVIS",
  // Claude
  "cloud": "Claude", "claud": "Claude", "clod": "Claude", "klaude": "Claude",
  "claw": "Claude", "clawed": "Claude", "klod": "Claude", "claude's": "Claude",
  "clot": "Claude",
  // Apps
  "no pad": "Notepad", "note pad": "Notepad", "not pad": "Notepad", "node pad": "Notepad",
  "chrome book": "Chrome", "crome": "Chrome", "grown": "Chrome", "krome": "Chrome",
  "be as code": "VS Code", "we ask code": "VS Code", "visa code": "VS Code",
  "v s code": "VS Code", "BS code": "VS Code",
  // Commands
  "screen short": "screenshot", "screen shut": "screenshot", "green shot": "screenshot",
  "snap shot": "snapshot",
  "desk top": "desktop", "death stop": "desktop", "death top": "desktop",
  "split scream": "split screen", "spit screen": "split screen",
  "nap": "snap", "snack": "snap",
  "wall paper": "wallpaper",
  "blue tooth": "Bluetooth", "blue to": "Bluetooth",
  "shut down": "shutdown", "shirt down": "shutdown",
  "night light": "night light",
  "calender": "calendar", "colander": "calendar",
  "whats up": "WhatsApp", "what's up": "WhatsApp", "what sap": "WhatsApp",
  "tell gram": "Telegram", "telegram": "Telegram",
  // Actions
  "clothes": "close", "clause": "close", "claws": "close",
  "lunch": "launch", "launch": "launch",
  "snatch": "snap", "snap to": "snap to",
  "maximize": "maximize", "minimise": "minimize", "minimalize": "minimize",
  "sweets": "switch", "switch to": "switch to",
  "create a": "create a", "great a": "create a",
  "full her": "folder", "boulder": "folder",
  "test holder": "TestFolder", "test folder": "TestFolder",
  // Habitat
  "habitat": "Habitat", "habited": "Habitat", "have it at": "Habitat",
  // Memory
  "mammary": "memory", "mammaries": "memories",
  // Numbers sometimes misheard
  "won": "one", "to": "two", "tree": "three", "for": "four",
  // Voice enrollment
  "in role": "enroll", "and roll": "enroll", "enrol": "enroll",
  "record my boys": "record my voice", "record your voice": "record my voice",
};

// Phrase-level corrections (applied before word-level)
const PHRASE_CORRECTIONS: [RegExp, string][] = [
  [/\bno pad\b/gi, "Notepad"],
  [/\bnote pad\b/gi, "Notepad"],
  [/\bnot pad\b/gi, "Notepad"],
  [/\bscreen ?shot\b/gi, "screenshot"],
  [/\bscreen ?shut\b/gi, "screenshot"],
  [/\bdesk ?top\b/gi, "desktop"],
  [/\bwall ?paper\b/gi, "wallpaper"],
  [/\bblue ?tooth\b/gi, "Bluetooth"],
  [/\bshut ?down\b/gi, "shutdown"],
  [/\bsplit ?screen\b/gi, "split screen"],
  [/\bnight ?light\b/gi, "night light"],
  [/\btest ?folder\b/gi, "TestFolder"],
  [/\bvs ?code\b/gi, "VS Code"],
  [/\bv ?s ?code\b/gi, "VS Code"],
  [/\bwhats ?app\b/gi, "WhatsApp"],
  [/\btele ?gram\b/gi, "Telegram"],
  [/\binternet ?speed\b/gi, "internet speed"],
  [/\bbattery ?saver\b/gi, "battery saver"],
];

function correctTranscript(text: string): string {
  let corrected = text;
  // Phrase corrections first
  for (const [pattern, replacement] of PHRASE_CORRECTIONS) {
    corrected = corrected.replace(pattern, replacement);
  }
  // Word corrections
  for (const [wrong, right] of Object.entries(WORD_CORRECTIONS)) {
    corrected = corrected.replace(new RegExp(`\\b${wrong}\\b`, "gi"), right);
  }
  return corrected;
}

function setState(newState: JarvisState): void {
  const prev = state;
  state = newState;
  stateEnteredAt = Date.now();
  console.log(`[state] ${prev} → ${newState}`);

  // Clear timeouts when leaving their respective states
  if (prev === "thinking" && thinkingTimeout) {
    clearTimeout(thinkingTimeout);
    thinkingTimeout = null;
  }
  if (prev === "speaking" && speakingTimeout) {
    clearTimeout(speakingTimeout);
    speakingTimeout = null;
  }

  switch (newState) {
    case "locked":
      setStatus("Click anywhere to enable voice");
      orb.setState("idle");
      micBtn.classList.remove("active");
      break;
    case "idle":
      setStatus("Say 'Hey JARVIS'...");
      orb.setState("idle");
      micBtn.classList.remove("active");
      stopBtn.style.display = "none";
      ensureRecognition();
      break;
    case "listening":
      setStatus("Listening...");
      orb.setState("listening");
      micBtn.classList.add("active");
      stopBtn.style.display = "none";
      ensureRecognition();
      break;
    case "thinking":
      setStatus("Thinking...");
      orb.setState("thinking");
      stopBtn.style.display = "block"; // Show STOP during thinking too
      // AUTO-RECOVERY: if stuck in thinking for 30 seconds, go back to listening
      thinkingTimeout = window.setTimeout(() => {
        if (state === "thinking") {
          console.warn("[recovery] Stuck in thinking — recovering to listening");
          addMessage("Sorry sir, I had trouble processing that. Please try again.", "assistant");
          setState("listening");
        }
      }, 30000);
      break;
    case "speaking":
      setStatus("Speaking...");
      orb.setState("speaking");
      stopBtn.style.display = "block";
      // Safety: force back to listening after 30 seconds max (increased for long responses)
      speakingTimeout = window.setTimeout(() => {
        if (state === "speaking") {
          console.warn("[recovery] Speaking too long — forcing back to listening");
          stopSpeaking();
        }
      }, 30000);
      break;
  }
}

function stopSpeaking(): void {
  // Works during speaking AND thinking — cancel anything in progress
  if (state !== "speaking" && state !== "thinking") return;
  tts.stop();
  player.stop();
  endStreamingMessage();
  stopBtn.style.display = "none";
  if (speakingTimeout) { clearTimeout(speakingTimeout); speakingTimeout = null; }
  if (thinkingTimeout) { clearTimeout(thinkingTimeout); thinkingTimeout = null; }
  lastSpeakTime = Date.now();
  setState("listening");
  setTimeout(() => forceRestartRecognition(), 500);
}

// Stop button click
stopBtn.addEventListener("click", (e) => {
  e.stopPropagation();
  stopSpeaking();
});

function isInCooldown(): boolean {
  return Date.now() - lastSpeakTime < 800;
}

// --- Speech Recognition (bulletproof) ---
const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
let recognition: any = null;

function createRecognition(): any {
  if (!SpeechRecognition) return null;
  const rec = new SpeechRecognition();
  rec.continuous = true;
  rec.interimResults = true;
  rec.lang = "en-US";

  rec.onresult = (event: any) => {
    // Recognition is alive — reset failure tracking
    recognitionFailCount = 0;
    lastRecognitionResult = Date.now();

    for (let i = event.resultIndex; i < event.results.length; i++) {
      const transcript = event.results[i][0].transcript.toLowerCase().trim();
      const isFinal = event.results[i].isFinal;

      if (isInCooldown()) continue;

      // STOP detection during speaking OR thinking
      if (state === "speaking" || state === "thinking") {
        if (STOP_WORDS.some((w) => transcript.includes(w))) {
          stopSpeaking();
        }
        continue;
      }
      if (isEnrolling) continue;

      // WAKE WORD during idle
      if (state === "idle") {
        if (WAKE_WORDS.some((w) => transcript.includes(w))) {
          console.log("[wake] Detected:", transcript);
          sfx.micOn();
          setState("listening");

          let cmd = transcript;
          for (const w of WAKE_WORDS) cmd = cmd.replace(w, "").trim();
          if (cmd.length > 2 && isFinal) sendCommand(cmd);
        }
        continue;
      }

      // COMMAND during listening — only real commands, not noise
      if (state === "listening" && isFinal) {
        const text = event.results[i][0].transcript.trim();
        let cmd = text;
        for (const w of WAKE_WORDS) cmd = cmd.replace(new RegExp(w, "gi"), "").trim();
        cmd = correctTranscript(cmd);
        // Ignore noise words — must be a real command (3+ chars, 2+ words or known action)
        const noise = ["hey", "hi", "ok", "um", "uh", "ah", "oh", "hmm", "hm", "yeah", "yes", "no", "the", "a", "an"];
        if (cmd.length < 3 || noise.includes(cmd.toLowerCase())) continue;
        sendCommand(cmd);
      }
    }
  };

  rec.onerror = (event: any) => {
    if (event.error === "no-speech" || event.error === "aborted") return;
    console.error("[speech] error:", event.error);
    recognitionFailCount++;

    if (event.error === "not-allowed") {
      micBlocked = true;
      setStatus("Microphone blocked — click mic to retry");
    }
  };

  rec.onend = () => {
    // Only restart if not locked and mic is not blocked
    if (state !== "locked" && !micBlocked) {
      // Use backoff: 300ms normally, up to 3s after repeated failures
      const delay = Math.min(300 * Math.pow(2, recognitionFailCount), 3000);
      setTimeout(() => ensureRecognition(), delay);
    }
  };

  return rec;
}

function forceRestartRecognition(): void {
  // Destroy and recreate recognition — used after TTS to guarantee mic works
  if (state === "locked") return;
  console.log("[speech] Force restarting recognition");
  if (recognition) {
    try { recognition.abort(); } catch (_) {}
  }
  recognition = createRecognition();
  recognitionFailCount = 0;
  if (recognition) {
    try { recognition.start(); } catch (_) {}
  }
}

function ensureRecognition(): void {
  if (state === "locked") return;

  // If mic was blocked, reset after 10 seconds (user may have granted permission)
  if (micBlocked && Date.now() - lastStartAttempt > 10000) {
    micBlocked = false;
  }
  if (micBlocked) return;

  // Debounce: don't attempt start more than once per 200ms
  const now = Date.now();
  if (now - lastStartAttempt < 200) return;
  lastStartAttempt = now;

  // If recognition has failed 5+ times in a row, destroy and recreate
  if (recognitionFailCount >= 5) {
    forceRestartRecognition();
    return;
  }

  if (!recognition) {
    recognition = createRecognition();
    if (!recognition) return;
  }

  try {
    recognition.start();
  } catch (_) {
    // Already running — fine
  }
}

recognition = createRecognition();

// --- Voice auth: continuous audio capture for verification ---
let isEnrolling = false;
let audioRecorder: MediaRecorder | null = null;
let audioChunks: Blob[] = [];
let audioStream: MediaStream | null = null;

async function startAudioCapture(): Promise<void> {
  if (audioRecorder) return;
  try {
    audioStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    audioRecorder = new MediaRecorder(audioStream, { mimeType: "audio/webm" });
    audioChunks = [];
    audioRecorder.ondataavailable = (e) => audioChunks.push(e.data);
    audioRecorder.start(500); // capture in 500ms chunks
  } catch (_) {}
}

function stopAndGetAudio(): Promise<string> {
  return new Promise((resolve) => {
    if (!audioRecorder || audioRecorder.state !== "recording") {
      resolve("");
      return;
    }
    audioRecorder.onstop = async () => {
      try {
        const blob = new Blob(audioChunks, { type: "audio/webm" });
        const arrayBuf = await blob.arrayBuffer();
        const audioCtx = new AudioContext();
        const audioBuffer = await audioCtx.decodeAudioData(arrayBuf);
        const wavBuffer = audioBufferToWav(audioBuffer);
        const base64 = btoa(String.fromCharCode(...new Uint8Array(wavBuffer)));
        audioCtx.close();
        resolve(base64);
      } catch (_) {
        resolve("");
      }
      audioChunks = [];
      audioRecorder = null;
    };
    audioRecorder.stop();
    if (audioStream) {
      audioStream.getTracks().forEach((t) => t.stop());
      audioStream = null;
    }
  });
}

async function recordAndEnroll(): Promise<void> {
  addMessage("Recording your voice for 5 seconds... Speak naturally.", "assistant");
  isEnrolling = true;

  // Stop speech recognition — it conflicts with MediaRecorder for mic access
  if (recognition) {
    try { recognition.abort(); } catch (_) {}
  }

  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: { sampleRate: 16000 } });

    // Try webm first, fall back to any supported format
    let mimeType = "audio/webm";
    if (!MediaRecorder.isTypeSupported(mimeType)) {
      mimeType = "audio/ogg";
      if (!MediaRecorder.isTypeSupported(mimeType)) {
        mimeType = ""; // let browser decide
      }
    }

    const options: MediaRecorderOptions = mimeType ? { mimeType } : {};
    const mediaRecorder = new MediaRecorder(stream, options);
    const chunks: Blob[] = [];

    mediaRecorder.ondataavailable = (e) => {
      if (e.data.size > 0) chunks.push(e.data);
    };

    mediaRecorder.onstop = async () => {
      stream.getTracks().forEach((t) => t.stop());

      try {
        const blob = new Blob(chunks);
        console.log(`[enroll] Recorded ${chunks.length} chunks, total ${blob.size} bytes`);

        if (blob.size < 1000) {
          addMessage("Recording was too short or empty. Please try again.", "assistant");
          isEnrolling = false;
          forceRestartRecognition();
          return;
        }

        // Convert to WAV using AudioContext
        const arrayBuf = await blob.arrayBuffer();
        const audioCtx = new AudioContext();
        const audioBuffer = await audioCtx.decodeAudioData(arrayBuf);
        console.log(`[enroll] Decoded: ${audioBuffer.duration.toFixed(1)}s, ${audioBuffer.sampleRate}Hz`);

        const wavBuffer = audioBufferToWav(audioBuffer);
        // Convert to base64 in chunks to avoid call stack overflow
        const uint8 = new Uint8Array(wavBuffer);
        let binary = "";
        const chunkSize = 8192;
        for (let i = 0; i < uint8.length; i += chunkSize) {
          binary += String.fromCharCode(...uint8.slice(i, i + chunkSize));
        }
        const base64 = btoa(binary);
        console.log(`[enroll] WAV base64 length: ${base64.length}`);

        addMessage("Processing your voiceprint...", "assistant");
        socket.send({ type: "enroll_voice", audio: base64 });
        audioCtx.close();
      } catch (err) {
        console.error("[enroll] Error converting audio:", err);
        addMessage(`Voice enrollment error: ${err}. Please try again.`, "assistant");
      }

      isEnrolling = false;
      // Restart speech recognition
      setTimeout(() => forceRestartRecognition(), 500);
    };

    mediaRecorder.onerror = (e) => {
      console.error("[enroll] MediaRecorder error:", e);
      addMessage("Recording failed. Please try again.", "assistant");
      isEnrolling = false;
      stream.getTracks().forEach((t) => t.stop());
      setTimeout(() => forceRestartRecognition(), 500);
    };

    // Record in 500ms chunks
    mediaRecorder.start(500);
    console.log("[enroll] Recording started...");

    // Stop after 5 seconds
    setTimeout(() => {
      if (mediaRecorder.state === "recording") {
        console.log("[enroll] Stopping recording...");
        mediaRecorder.stop();
      }
    }, 5000);
  } catch (e) {
    console.error("[enroll] getUserMedia error:", e);
    addMessage(`Could not access microphone: ${e}`, "assistant");
    isEnrolling = false;
    setTimeout(() => forceRestartRecognition(), 500);
  }
}

function audioBufferToWav(buffer: AudioBuffer): ArrayBuffer {
  const numChannels = 1;
  const sampleRate = buffer.sampleRate;
  const format = 1; // PCM
  const bitDepth = 16;
  const data = buffer.getChannelData(0);
  const dataLength = data.length * (bitDepth / 8);
  const headerLength = 44;
  const wav = new ArrayBuffer(headerLength + dataLength);
  const view = new DataView(wav);

  // WAV header
  const writeString = (offset: number, str: string) => {
    for (let i = 0; i < str.length; i++) view.setUint8(offset + i, str.charCodeAt(i));
  };
  writeString(0, "RIFF");
  view.setUint32(4, 36 + dataLength, true);
  writeString(8, "WAVE");
  writeString(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, format, true);
  view.setUint16(22, numChannels, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * numChannels * (bitDepth / 8), true);
  view.setUint16(32, numChannels * (bitDepth / 8), true);
  view.setUint16(34, bitDepth, true);
  writeString(36, "data");
  view.setUint32(40, dataLength, true);

  // Write audio data
  let offset = 44;
  for (let i = 0; i < data.length; i++) {
    const sample = Math.max(-1, Math.min(1, data[i]));
    view.setInt16(offset, sample < 0 ? sample * 0x8000 : sample * 0x7FFF, true);
    offset += 2;
  }

  return wav;
}

function sendCommand(text: string): void {
  // Check for voice enrollment — fix mishearings of "voice" first
  let lower = text.toLowerCase();
  // "voice" gets misheard as: watch, boys, was, wise, wash, worse, wars
  lower = lower.replace(/\b(save|record|enroll|train|lock|register|learn)\s+(my|your|the)\s+(watch|boys|was|wise|wash|worse|wars|vase|bus|boss)\b/gi,
    (_, action, pronoun, __) => `${action} ${pronoun} voice`);

  const enrollPhrases = [
    "enroll my voice", "enroll voice", "record my voice", "record your voice",
    "record voice", "register my voice", "register voice",
    "voice lock", "voice enroll", "voice enrollment", "lock my voice",
    "set up voice", "setup voice", "voice recognition", "recognize my voice",
    "only my voice", "voice authentication", "voice auth",
    "save my voice", "learn my voice", "train my voice", "train voice",
    "my voice only", "voice security", "voice id", "voice identify",
    "lock jarvis", "secure jarvis", "jarvis only me",
    "save my watch", "record my watch", "save voice", "record my boys",
  ];
  if (enrollPhrases.some(p => lower.includes(p))) {
    recordAndEnroll();
    return;
  }
  const disablePhrases = ["disable voice", "remove voice lock", "unlock voice", "voice auth off"];
  if (disablePhrases.some(p => lower.includes(p))) {
    socket.send({ type: "disable_voice_auth" });
    addMessage("Disabling voice authentication...", "user");
    setState("thinking");
    return;
  }

  addMessage(text, "user");
  if (!socket.isConnected()) {
    addMessage("Connection lost — your command has been queued.", "assistant");
  }
  socket.send({ type: "transcript", text });
  setState("thinking");
  sfx.thinking();
}

// --- Audio callbacks ---
player.onEnd(() => {
  if (state === "speaking") {
    stopBtn.style.display = "none";
    if (speakingTimeout) { clearTimeout(speakingTimeout); speakingTimeout = null; }
    lastSpeakTime = Date.now();
    setState("listening");
    // Force restart recognition after audio playback
    setTimeout(() => forceRestartRecognition(), 300);
  }
});

// After browser TTS ends, Chrome's SpeechRecognition is dead.
// Must force-recreate recognition with a delay to let Chrome release audio.
tts.onEnd(() => {
  if (state === "speaking") {
    stopBtn.style.display = "none";
    if (speakingTimeout) { clearTimeout(speakingTimeout); speakingTimeout = null; }
    lastSpeakTime = Date.now();
    setState("listening");
    // CRITICAL: Chrome kills recognition during TTS — force restart after delay
    setTimeout(() => forceRestartRecognition(), 500);
  }
});

// --- WebSocket ---
socket.on("connected", () => {
  sfx.connected();
  if (state !== "locked") {
    setState("idle");
  }
});

socket.on("disconnected", () => {
  setStatus("Reconnecting...");
  orb.setState("idle");
});

socket.on("status", (data) => {
  if ((data.text as string) === "thinking" && state !== "speaking") {
    setState("thinking");
  }
});

// --- Non-streaming response (quick commands, personality, errors) ---
socket.on("response", async (data) => {
  const text = data.text as string;
  const audio = data.audio as string | undefined;

  if (thinkingTimeout) {
    clearTimeout(thinkingTimeout);
    thinkingTimeout = null;
  }

  addMessage(text, "assistant");
  sfx.response();
  setState("speaking");

  if (audio) {
    try {
      await player.playBase64(audio);
    } catch (e) {
      console.error("[audio] error:", e);
      if (state === "speaking") {
        lastSpeakTime = Date.now();
        setState("listening");
      }
    }
  } else {
    // No audio — text already shown, go to listening
    lastSpeakTime = Date.now();
    setState("listening");
    setTimeout(() => forceRestartRecognition(), 300);
  }
});

// --- Streaming response (main AI pipeline) ---
let streamFullText = "";

socket.on("stream_start", () => {
  if (thinkingTimeout) {
    clearTimeout(thinkingTimeout);
    thinkingTimeout = null;
  }
  sfx.response();
  setState("speaking");
  startStreamingMessage();
  streamFullText = "";
});

socket.on("stream_chunk", (data) => {
  const text = data.text as string;
  appendStreamChunk(text);
  streamFullText += text;
});

socket.on("stream_end", (data) => {
  endStreamingMessage();
  streamFullText = (data.text as string) || streamFullText;
  // Audio will arrive separately — stay in "speaking" state
});

socket.on("audio", async (data) => {
  const audio = data.audio as string;
  try {
    await player.playBase64(audio);
  } catch (e) {
    console.error("[audio] playback error:", e);
    if (state === "speaking") {
      lastSpeakTime = Date.now();
      setState("listening");
    }
  }
});

socket.on("no_audio", () => {
  // No ElevenLabs audio — text already shown via streaming, go back to listening
  if (state === "speaking") {
    lastSpeakTime = Date.now();
    setState("listening");
    setTimeout(() => forceRestartRecognition(), 300);
  }
});

socket.on("error", (data) => {
  console.error("[jarvis]", data.text);
  sfx.error();
  endStreamingMessage();
  setState("listening");
});

// --- Voice auth handlers ---
socket.on("voice_auth_result", (data) => {
  if (data.success) {
    addMessage("Voice enrolled successfully. I'll now only respond to your voice, sir.", "assistant");
  } else {
    addMessage(`Voice enrollment failed: ${data.error}`, "assistant");
  }
  setState("listening");
});

socket.on("voice_verify_result", (data) => {
  if (!data.verified) {
    addMessage("Voice not recognized. Access denied.", "assistant");
  }
});

// --- Theme change handler ---
socket.on("theme", (data) => {
  const theme = data.theme as string;
  orb.setTheme(theme as any);
});

socket.connect();

// --- WebSocket heartbeat — keeps connection alive ---
setInterval(() => {
  socket.send({ type: "ping" });
}, 15000);

// --- Recognition watchdog — restart if it dies ---
setInterval(() => {
  if (state !== "locked") {
    ensureRecognition();
  }
}, 3000);

// --- GLOBAL RECOVERY WATCHDOG — last resort for ANY stuck state ---
setInterval(() => {
  if (state === "locked" || state === "idle" || state === "listening") return;
  const elapsed = Date.now() - stateEnteredAt;
  // If stuck in thinking for >35s or speaking for >35s, force recovery
  if (elapsed > 35000) {
    console.warn(`[watchdog] Stuck in "${state}" for ${Math.round(elapsed / 1000)}s — forcing recovery`);
    if (state === "speaking") stopSpeaking();
    else setState("listening");
  }
}, 5000);

// --- Recognition health check — detect if recognition is alive but not producing results ---
setInterval(() => {
  if (state === "locked") return;
  const silentFor = Date.now() - lastRecognitionResult;
  // If no results for 60 seconds while we should be listening, recreate
  if (silentFor > 60000 && (state === "idle" || state === "listening")) {
    console.warn("[watchdog] No speech results for 60s — recreating recognition");
    recognitionFailCount = 5; // force recreation
    ensureRecognition();
  }
}, 15000);

// --- Mic Button ---
micBtn.addEventListener("click", () => {
  if (state === "locked") {
    setState("idle");
    micBlocked = false; // reset on user interaction — they may have granted permission
    recognitionFailCount = 0;
    ensureRecognition();
    return;
  }
  if (state === "speaking") {
    stopSpeaking();
    return;
  }
  if (state === "listening") {
    setState("idle");
    sfx.micOff();
  } else {
    setState("listening");
    sfx.micOn();
  }
});

// --- Keyboard Shortcuts ---
document.addEventListener("keydown", (e) => {
  if (e.code === "Space" && e.target === document.body) {
    e.preventDefault();
    micBtn.click();
  }
  if (e.code === "F11") {
    e.preventDefault();
    document.fullscreenElement ? document.exitFullscreen() : document.documentElement.requestFullscreen();
  }
  if (e.code === "Escape") {
    stopSpeaking();
  }
});

// Removed "click anywhere to stop" — was too aggressive, interfered with normal clicks

// --- Auto-unlock: no click needed, JARVIS starts listening on its own ---
function unlock(): void {
  if (state !== "locked") return;
  setState("idle");
  ensureRecognition();
}
// Still allow click/key to unlock immediately
document.addEventListener("click", () => unlock(), { once: true });
document.addEventListener("keydown", () => unlock(), { once: true });
// Auto-unlock after 2 seconds — JARVIS wakes up on its own
setTimeout(() => unlock(), 2000);

// --- Background survival — restart recognition when tab regains focus ---
document.addEventListener("visibilitychange", () => {
  if (!document.hidden && state !== "locked") {
    console.log("[background] Tab visible again — force restarting recognition");
    forceRestartRecognition();
  }
});

// --- Keep alive in background — prevent Chrome from suspending ---
// Play silent audio to keep audio context alive (prevents tab suspension)
setInterval(() => {
  if (state !== "locked" && document.hidden) {
    // Tiny silent oscillator keeps the tab alive
    try {
      const ctx = new AudioContext();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      gain.gain.value = 0; // completely silent
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start();
      setTimeout(() => { osc.stop(); ctx.close(); }, 100);
    } catch (_) {}
  }
}, 20000);

// --- Fullscreen ---
document.getElementById("title")?.addEventListener("dblclick", () => {
  document.fullscreenElement ? document.exitFullscreen() : document.documentElement.requestFullscreen();
});

setState("locked");
