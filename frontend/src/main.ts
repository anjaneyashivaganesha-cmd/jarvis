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
const socket = new JarvisSocket();

// --- State machine ---
type JarvisState = "locked" | "idle" | "listening" | "thinking" | "speaking";
let state: JarvisState = "locked";
let lastSpeakTime = 0;

const WAKE_WORDS = ["jarvis", "hey jarvis", "ok jarvis", "yo jarvis", "hi jarvis", "hello jarvis"];
const STOP_WORDS = ["stop", "stop jarvis", "shut up", "quiet", "enough", "stop talking",
  "ok stop", "jarvis stop", "hey jarvis stop", "wait", "jarvis wait",
  "hey jarvis wait", "hold on", "pause"];

function setState(newState: JarvisState): void {
  console.log(`[state] ${state} → ${newState}`);
  state = newState;
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
      break;
    case "listening":
      setStatus("Listening...");
      orb.setState("listening");
      micBtn.classList.add("active");
      break;
    case "thinking":
      setStatus("Thinking...");
      orb.setState("thinking");
      break;
    case "speaking":
      setStatus("Speaking... (click mic or say 'stop')");
      orb.setState("speaking");
      break;
  }
}

function stopSpeaking(): void {
  if (state !== "speaking") return;
  tts.stop();
  player.stop();
  lastSpeakTime = Date.now();
  setState("listening");
}

function isInCooldown(): boolean {
  return Date.now() - lastSpeakTime < 2000;
}

// --- Speech Recognition ---
const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
let recognition: any = null;
let recognitionRunning = false;

function ensureRecognition(): void {
  if (!recognition || recognitionRunning) return;
  try {
    recognition.start();
    recognitionRunning = true;
  } catch (_) {
    // Already running
    recognitionRunning = true;
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

      // Ignore during cooldown (prevents echo after stopping)
      if (isInCooldown()) continue;

      // STOP detection — works during speaking
      if (state === "speaking") {
        if (STOP_WORDS.some((w) => transcript.includes(w))) {
          console.log("[stop] Voice:", transcript);
          stopSpeaking();
        }
        continue; // Ignore all non-stop input while speaking
      }

      // WAKE WORD detection — works during idle
      if (state === "idle") {
        if (WAKE_WORDS.some((w) => transcript.includes(w))) {
          console.log("[wake] Detected:", transcript);
          sfx.micOn();
          setState("listening");

          // Extract command after wake word
          let cmd = transcript;
          for (const w of WAKE_WORDS) {
            cmd = cmd.replace(w, "").trim();
          }
          if (cmd.length > 2 && isFinal) {
            sendCommand(cmd);
          }
        }
        continue;
      }

      // COMMAND processing — works during listening
      if (state === "listening" && isFinal) {
        const text = event.results[i][0].transcript.trim();
        let cmd = text;
        for (const w of WAKE_WORDS) {
          cmd = cmd.replace(new RegExp(w, "gi"), "").trim();
        }
        if (cmd.length > 1) {
          sendCommand(cmd);
        }
      }
    }
  };

  recognition.onerror = (event: any) => {
    if (event.error !== "no-speech" && event.error !== "aborted") {
      console.error("[speech] error:", event.error);
    }
    recognitionRunning = false;
  };

  recognition.onend = () => {
    recognitionRunning = false;
    // Always restart unless locked
    if (state !== "locked") {
      setTimeout(ensureRecognition, 300);
    }
  };
}

function sendCommand(text: string): void {
  addMessage(text, "user");
  socket.send({ type: "transcript", text });
  setState("thinking");
  sfx.thinking();
}

// --- Audio player end callback ---
player.onEnd(() => {
  if (state === "speaking") {
    lastSpeakTime = Date.now();
    setState("listening");
  }
});

// --- Browser TTS callbacks ---
tts.onStart(() => {
  setState("speaking");
});

tts.onEnd(() => {
  if (state === "speaking") {
    lastSpeakTime = Date.now();
    setState("listening");
  }
});

// --- WebSocket events ---
socket.on("connected", () => {
  sfx.connected();
  if (state === "locked") {
    setState("locked"); // Keep locked until first click
  } else {
    setState("idle");
    ensureRecognition();
  }
});

socket.on("disconnected", () => {
  setStatus("Reconnecting...");
  orb.setState("idle");
});

socket.on("status", (data) => {
  if ((data.text as string) === "thinking") {
    setState("thinking");
  }
});

socket.on("response", async (data) => {
  const text = data.text as string;
  const audio = data.audio as string | undefined;

  addMessage(text, "assistant");
  sfx.response();

  if (audio) {
    setState("speaking");
    try {
      await player.playBase64(audio);
    } catch (e) {
      console.error("[audio] error:", e);
      // If playback fails, go back to listening
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

// --- Mic Button ---
micBtn.addEventListener("click", () => {
  if (state === "locked") {
    // First click unlocks
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
    ensureRecognition();
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

// --- First click/key unlocks mic ---
function unlockOnInteraction(): void {
  if (state !== "locked") return;
  setState("idle");
  ensureRecognition();
  document.removeEventListener("click", unlockOnInteraction);
  document.removeEventListener("keydown", unlockOnKey);
}
function unlockOnKey(): void { unlockOnInteraction(); }
document.addEventListener("click", unlockOnInteraction);
document.addEventListener("keydown", unlockOnKey);

// --- Fullscreen on title double-click ---
document.getElementById("title")?.addEventListener("dblclick", () => {
  document.fullscreenElement ? document.exitFullscreen() : document.documentElement.requestFullscreen();
});

// --- Initial state ---
setState("locked");
