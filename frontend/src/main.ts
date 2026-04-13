import { JarvisSocket } from "./websocket";
import { SpeechInput } from "./speech";
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

tts.onStart(() => {
  orb.setState("speaking");
  setStatus("Speaking...");
  if (speech.isListening()) {
    speech.toggle();
    micBtn.classList.remove("active");
  }
});

tts.onEnd(() => {
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
  sfx.connected();
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

  if (audio) {
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
micBtn.addEventListener("click", () => {
  const isListening = speech.toggle();
  micBtn.classList.toggle("active", isListening);

  if (isListening) {
    setStatus("Listening...");
    orb.setState("listening");
    sfx.micOn();
  } else {
    setStatus("Click the mic to start");
    orb.setState("idle");
    sfx.micOff();
  }
});

// --- Keyboard Shortcuts ---
document.addEventListener("keydown", (e) => {
  // Space = toggle mic
  if (e.code === "Space" && e.target === document.body) {
    e.preventDefault();
    micBtn.click();
  }
  // F11 = fullscreen
  if (e.code === "F11") {
    e.preventDefault();
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen();
    } else {
      document.exitFullscreen();
    }
  }
  // Escape = stop speaking
  if (e.code === "Escape") {
    tts.stop();
    setStatus(speech.isListening() ? "Listening..." : "Click the mic to start");
    orb.setState(speech.isListening() ? "listening" : "idle");
  }
});

// --- Fullscreen button ---
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
