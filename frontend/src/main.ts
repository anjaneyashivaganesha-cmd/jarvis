import { JarvisSocket } from "./websocket";
import { AudioPlayer } from "./audio";
import { BrowserTTS } from "./tts";
import { ParticleOrb } from "./orb";
import { SoundEffects } from "./sounds";
import { addMessage, setStatus } from "./ui";

// --- Particle Orb ---
const orbContainer = document.getElementById("orb-container")!;
const orb = new ParticleOrb(orbContainer);

// --- Audio Player ---
const player = new AudioPlayer();

// --- Sound Effects ---
const sfx = new SoundEffects();

// --- Browser TTS ---
const tts = new BrowserTTS();
const micBtn = document.getElementById("mic-btn")!;

// --- State ---
let isActive = false; // mic is active (listening for commands)
let isAlwaysOn = true; // always-on mode (wake word detection)
let isSpeaking = false;
let isBrowserTTS = false; // true = browser TTS (mic blocked), false = ElevenLabs (mic works)
let cooldown = false;
let currentResponseText = ""; // to filter echo

const WAKE_WORDS = ["jarvis", "hey jarvis", "ok jarvis", "yo jarvis", "hi jarvis", "hello jarvis"];
const STOP_WORDS = ["stop", "stop jarvis", "shut up", "quiet", "enough", "stop talking", "ok stop", "jarvis stop", "hey jarvis stop", "wait", "jarvis wait", "hey jarvis wait", "hold on", "pause"];

// --- Speech Recognition (single instance for both wake word + commands) ---
const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
let recognition: any = null;

if (SpeechRecognition) {
  recognition = new SpeechRecognition();
  recognition.continuous = true;
  recognition.interimResults = true;
  recognition.lang = "en-US";

  recognition.onresult = (event: any) => {
    for (let i = event.resultIndex; i < event.results.length; i++) {
      const transcript = event.results[i][0].transcript.toLowerCase().trim();
      const isFinal = event.results[i].isFinal;

      // Cooldown — ignore all input for 2 seconds after stopping speech
      if (cooldown) continue;

      // While speaking — check for stop commands
      if (isSpeaking) {
        if (STOP_WORDS.some((w) => transcript.includes(w))) {
          console.log("[stop] Voice stop detected:", transcript);
          tts.stop();
          try { player.stop(); } catch (_) {}
          isSpeaking = false;
          isBrowserTTS = false;
          cooldown = true;
          setTimeout(() => { cooldown = false; }, 2000);
          setStatus(isActive ? "Listening..." : "Say 'Hey JARVIS'...");
          orb.setState(isActive ? "listening" : "idle");
        }
        // Filter echo — ignore if transcript matches part of JARVIS response
        continue;
      }

      if (!isActive) {
        // Wake word detection mode
        if (WAKE_WORDS.some((w) => transcript.includes(w))) {
          console.log("[wake] Detected:", transcript);
          activateMic();

          // Extract command after wake word (e.g., "hey jarvis what time is it")
          let command = transcript;
          for (const w of WAKE_WORDS) {
            command = command.replace(w, "").trim();
          }
          // If there's a command after the wake word and it's final, send it
          if (command.length > 2 && isFinal) {
            addMessage(command, "user");
            socket.send({ type: "transcript", text: command });
            orb.setState("thinking");
            setStatus("Thinking...");
          }
        }
      } else {
        // Active listening mode — process commands
        if (isFinal) {
          const text = event.results[i][0].transcript.trim();
          // Filter out wake words from the command
          let cleanText = text;
          for (const w of WAKE_WORDS) {
            cleanText = cleanText.replace(new RegExp(w, "gi"), "").trim();
          }
          if (cleanText.length > 1) {
            addMessage(cleanText, "user");
            socket.send({ type: "transcript", text: cleanText });
            orb.setState("thinking");
            setStatus("Thinking...");
          }
        }
      }
    }
  };

  recognition.onerror = (event: any) => {
    if (event.error !== "no-speech" && event.error !== "aborted") {
      console.error("[speech] error:", event.error);
    }
  };

  recognition.onend = () => {
    // Auto-restart if we're supposed to be listening
    if (isActive || isAlwaysOn) {
      setTimeout(() => {
        try { recognition.start(); } catch (_) {}
      }, 200);
    }
  };
}

function activateMic(): void {
  if (isActive) return;
  isActive = true;
  micBtn.classList.add("active");
  setStatus("Listening...");
  orb.setState("listening");
  sfx.micOn();
}

function deactivateMic(): void {
  isActive = false;
  micBtn.classList.remove("active");
  if (isAlwaysOn) {
    setStatus("Say 'Hey JARVIS'...");
  } else {
    setStatus("Click the mic to start");
  }
  orb.setState("idle");
  sfx.micOff();
}

// Start always-on listening
function startListening(): void {
  if (!recognition) return;
  try {
    recognition.start();
    if (isAlwaysOn && !isActive) {
      setStatus("Say 'Hey JARVIS'...");
    }
  } catch (_) {}
}

// --- TTS callbacks ---
tts.onStart(() => {
  isSpeaking = true;
  orb.setState("speaking");
  setStatus("Speaking... (click mic or press Esc to stop)");
});

tts.onEnd(() => {
  isSpeaking = false;
  if (isActive) {
    setStatus("Listening...");
    orb.setState("listening");
  } else if (isAlwaysOn) {
    setStatus("Say 'Hey JARVIS'...");
    orb.setState("idle");
  }
});

// --- WebSocket ---
const socket = new JarvisSocket();

socket.on("connected", () => {
  orb.setState("idle");
  sfx.connected();
  if (micUnlocked) {
    setStatus("Say 'Hey JARVIS'...");
    startListening();
  } else {
    setStatus("Click anywhere to enable voice");
  }
});

socket.on("disconnected", () => {
  setStatus("Reconnecting...");
  orb.setState("idle");
});

socket.on("status", (data) => {
  const text = data.text as string;
  if (text === "thinking") {
    setStatus("Thinking...");
    orb.setState("thinking");
    sfx.thinking();
  }
});

socket.on("response", async (data) => {
  const text = data.text as string;
  const audio = data.audio as string | undefined;

  addMessage(text, "assistant");
  sfx.response();

  currentResponseText = text.toLowerCase();

  if (audio) {
    // ElevenLabs — mic stays active, can hear "stop"
    isSpeaking = true;
    isBrowserTTS = false;
    orb.setState("speaking");
    setStatus("Speaking... (say 'stop' or click mic)");
    try {
      await player.playBase64(audio);
    } catch (e) {
      console.error("[audio] playback error:", e);
    }
    isSpeaking = false;
    cooldown = true;
    setTimeout(() => { cooldown = false; }, 1500);
    if (isActive) {
      setStatus("Listening...");
      orb.setState("listening");
    } else {
      setStatus(isAlwaysOn ? "Say 'Hey JARVIS'..." : "Click the mic to start");
      orb.setState("idle");
    }
  } else {
    // Browser TTS — mic blocked by Chrome, can only stop via button/Escape
    isBrowserTTS = true;
    tts.speak(text);
  }
});

socket.on("error", (data) => {
  console.error("[jarvis]", data.text);
  setStatus("Error occurred");
  orb.setState("idle");
  sfx.error();
});

socket.connect();

// --- Mic Button ---
micBtn.addEventListener("click", () => {
  // If speaking, stop speech first
  if (isSpeaking) {
    tts.stop();
    try { player.stop(); } catch (_) {}
    isSpeaking = false;
    cooldown = true;
    setTimeout(() => { cooldown = false; }, 2000);
    setStatus("Listening...");
    orb.setState("listening");
    isActive = true;
    micBtn.classList.add("active");
    return;
  }

  if (isActive) {
    deactivateMic();
  } else {
    activateMic();
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
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen();
    } else {
      document.exitFullscreen();
    }
  }
  if (e.code === "Escape") {
    tts.stop();
    try { player.stop(); } catch (_) {}
    isSpeaking = false;
    cooldown = true;
    setTimeout(() => { cooldown = false; }, 2000);
    if (isActive) {
      setStatus("Listening...");
      orb.setState("listening");
    } else {
      setStatus(isAlwaysOn ? "Say 'Hey JARVIS'..." : "Click the mic to start");
      orb.setState("idle");
    }
  }
});

// --- Fullscreen on title double-click ---
const title = document.getElementById("title");
if (title) {
  title.addEventListener("dblclick", () => {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen();
    } else {
      document.exitFullscreen();
    }
  });
}

// --- Auto-start mic on first user interaction (Chrome requires a click first) ---
let micUnlocked = false;
function unlockMic(): void {
  if (micUnlocked) return;
  micUnlocked = true;
  startListening();
  document.removeEventListener("click", unlockMic);
  document.removeEventListener("keydown", unlockMicKey);
}
function unlockMicKey(e: KeyboardEvent): void {
  unlockMic();
}
document.addEventListener("click", unlockMic);
document.addEventListener("keydown", unlockMicKey);

// Show hint
setStatus("Click anywhere to enable voice");
