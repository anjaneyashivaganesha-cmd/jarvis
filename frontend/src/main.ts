import { JarvisSocket } from "./websocket";
import { AudioPlayer } from "./audio";
import { BrowserTTS } from "./tts";
import { ParticleOrb } from "./orb";
import { SoundEffects } from "./sounds";
import { addMessage, setStatus } from "./ui";

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

const WAKE_WORDS = ["jarvis", "hey jarvis", "ok jarvis", "yo jarvis", "hi jarvis", "hello jarvis"];
const STOP_WORDS = ["stop", "stop jarvis", "shut up", "quiet", "enough", "stop talking",
  "ok stop", "jarvis stop", "hey jarvis stop", "wait", "jarvis wait",
  "hey jarvis wait", "hold on", "pause"];

function setState(newState: JarvisState): void {
  const prev = state;
  state = newState;
  console.log(`[state] ${prev} → ${newState}`);

  // Clear thinking timeout when leaving thinking state
  if (prev === "thinking" && thinkingTimeout) {
    clearTimeout(thinkingTimeout);
    thinkingTimeout = null;
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
      ensureRecognition();
      break;
    case "listening":
      setStatus("Listening...");
      orb.setState("listening");
      micBtn.classList.add("active");
      ensureRecognition();
      break;
    case "thinking":
      setStatus("Thinking...");
      orb.setState("thinking");
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
      // Safety: force back to listening after 20 seconds max
      if (speakingTimeout) clearTimeout(speakingTimeout);
      speakingTimeout = window.setTimeout(() => {
        if (state === "speaking") {
          console.warn("[recovery] Speaking too long — forcing back to listening");
          stopSpeaking();
        }
      }, 20000);
      break;
  }
}

function stopSpeaking(): void {
  if (state !== "speaking") return;
  tts.stop();
  player.stop();
  stopBtn.style.display = "none";
  if (speakingTimeout) { clearTimeout(speakingTimeout); speakingTimeout = null; }
  lastSpeakTime = Date.now();
  setState("listening");
}

// Stop button click
stopBtn.addEventListener("click", (e) => {
  e.stopPropagation();
  stopSpeaking();
});

function isInCooldown(): boolean {
  return Date.now() - lastSpeakTime < 1500; // Reduced from 2s to 1.5s
}

// --- Speech Recognition ---
const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
let recognition: any = null;

function ensureRecognition(): void {
  if (!recognition || state === "locked") return;
  try {
    recognition.start();
  } catch (_) {
    // Already running — this is fine
  }
}

if (SpeechRecognition) {
  recognition = new SpeechRecognition();
  recognition.continuous = true;
  recognition.interimResults = true;
  recognition.lang = "en-US";

  recognition.onresult = (event: any) => {
    for (let i = event.resultIndex; i < event.results.length; i++) {
      const transcript = event.results[i][0].transcript.toLowerCase().trim();
      const isFinal = event.results[i].isFinal;

      if (isInCooldown()) continue;

      // STOP detection during speaking
      if (state === "speaking") {
        if (STOP_WORDS.some((w) => transcript.includes(w))) {
          stopSpeaking();
        }
        continue;
      }

      // Ignore input while thinking
      if (state === "thinking") continue;

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

      // COMMAND during listening
      if (state === "listening" && isFinal) {
        const text = event.results[i][0].transcript.trim();
        let cmd = text;
        for (const w of WAKE_WORDS) cmd = cmd.replace(new RegExp(w, "gi"), "").trim();
        if (cmd.length > 1) sendCommand(cmd);
      }
    }
  };

  recognition.onerror = (event: any) => {
    if (event.error !== "no-speech" && event.error !== "aborted") {
      console.error("[speech] error:", event.error);
    }
  };

  recognition.onend = () => {
    // ALWAYS restart unless locked — this is the key reliability fix
    if (state !== "locked") {
      setTimeout(ensureRecognition, 200);
    }
  };
}

function sendCommand(text: string): void {
  addMessage(text, "user");
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
  }
});

tts.onStart(() => setState("speaking"));
tts.onEnd(() => {
  if (state === "speaking") {
    stopBtn.style.display = "none";
    if (speakingTimeout) { clearTimeout(speakingTimeout); speakingTimeout = null; }
    lastSpeakTime = Date.now();
    setState("listening");
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

socket.on("response", async (data) => {
  const text = data.text as string;
  const audio = data.audio as string | undefined;

  // Clear thinking timeout
  if (thinkingTimeout) {
    clearTimeout(thinkingTimeout);
    thinkingTimeout = null;
  }

  addMessage(text, "assistant");
  sfx.response();

  if (audio) {
    setState("speaking");
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
    tts.speak(text);
  }
});

socket.on("error", (data) => {
  console.error("[jarvis]", data.text);
  sfx.error();
  setState("listening");
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

// --- Mic Button ---
micBtn.addEventListener("click", () => {
  if (state === "locked") {
    setState("idle");
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

// --- Tap ANYWHERE to stop speaking (whole page) ---
document.addEventListener("click", (e) => {
  if (state === "speaking") {
    e.preventDefault();
    e.stopPropagation();
    stopSpeaking();
  }
}, true);

// --- First interaction unlocks ---
function unlock(): void {
  if (state !== "locked") return;
  setState("idle");
  ensureRecognition();
  document.removeEventListener("click", unlock);
  document.removeEventListener("keydown", unlock);
}
document.addEventListener("click", unlock);
document.addEventListener("keydown", unlock);

// --- Fullscreen ---
document.getElementById("title")?.addEventListener("dblclick", () => {
  document.fullscreenElement ? document.exitFullscreen() : document.documentElement.requestFullscreen();
});

setState("locked");
