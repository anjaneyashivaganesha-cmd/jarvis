import { JarvisSocket } from "./websocket";
import { SpeechInput } from "./speech";
import { AudioPlayer } from "./audio";
import { BrowserTTS } from "./tts";
import { ParticleOrb } from "./orb";
import { addMessage, setStatus } from "./ui";

// --- Particle Orb ---
const orbContainer = document.getElementById("orb-container")!;
const orb = new ParticleOrb(orbContainer);

// --- Audio Player ---
const player = new AudioPlayer();

// --- Browser TTS ---
const tts = new BrowserTTS();

tts.onStart(() => {
  orb.setState("speaking");
  setStatus("Speaking...");
  // Pause mic while speaking to avoid feedback
  if (speech.isListening()) {
    speech.toggle();
    micBtn.classList.remove("active");
  }
});

tts.onEnd(() => {
  // Auto-resume listening after speaking
  if (!speech.isListening()) {
    speech.toggle();
    micBtn.classList.add("active");
    setStatus("Listening...");
    orb.setState("listening");
  }
});

// --- WebSocket ---
const socket = new JarvisSocket();

socket.on("connected", () => {
  setStatus("Connected to JARVIS");
  orb.setState("idle");
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
  }
});

socket.on("response", async (data) => {
  const text = data.text as string;
  const audio = data.audio as string | undefined;

  addMessage(text, "assistant");

  if (audio) {
    // ElevenLabs TTS (premium)
    orb.setState("speaking");
    setStatus("Speaking...");
    try {
      await player.playBase64(audio);
    } catch (e) {
      console.error("[audio] playback error:", e);
    }
    if (speech.isListening()) {
      setStatus("Listening...");
      orb.setState("listening");
    } else {
      setStatus("Click the mic to start");
      orb.setState("idle");
    }
  } else {
    // Browser TTS (free)
    tts.speak(text);
  }
});

socket.on("error", (data) => {
  console.error("[jarvis]", data.text);
  setStatus("Error occurred");
  orb.setState("idle");
});

socket.connect();

// --- Speech Recognition ---
const speech = new SpeechInput((text, isFinal) => {
  if (isFinal) {
    addMessage(text, "user");
    socket.send({ type: "transcript", text });
    orb.setState("thinking");
    setStatus("Thinking...");
  }
});

// --- Mic Button ---
const micBtn = document.getElementById("mic-btn")!;

micBtn.addEventListener("click", () => {
  const isListening = speech.toggle();
  micBtn.classList.toggle("active", isListening);

  if (isListening) {
    setStatus("Listening...");
    orb.setState("listening");
  } else {
    setStatus("Click the mic to start");
    orb.setState("idle");
  }
});

// --- Keyboard shortcut: Space to toggle mic ---
document.addEventListener("keydown", (e) => {
  if (e.code === "Space" && e.target === document.body) {
    e.preventDefault();
    micBtn.click();
  }
});
