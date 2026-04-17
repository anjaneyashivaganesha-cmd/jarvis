const transcript = document.getElementById("transcript")!;
const status = document.getElementById("status")!;

let streamingEl: HTMLDivElement | null = null;

export function setStatus(text: string): void {
  status.textContent = text;
}

export function addMessage(text: string, role: "user" | "assistant"): void {
  const div = document.createElement("div");
  div.className = `msg ${role}`;
  div.textContent = text;
  transcript.appendChild(div);
  transcript.scrollTop = transcript.scrollHeight;
}

/** Create an empty assistant message bubble for streaming text into */
export function startStreamingMessage(): void {
  endStreamingMessage(); // clean up any previous
  const div = document.createElement("div");
  div.className = "msg assistant streaming";
  transcript.appendChild(div);
  transcript.scrollTop = transcript.scrollHeight;
  streamingEl = div;
}

/** Append a text chunk to the current streaming message */
export function appendStreamChunk(text: string): void {
  if (streamingEl) {
    streamingEl.textContent += text;
    transcript.scrollTop = transcript.scrollHeight;
  }
}

/** Finalize the streaming message */
export function endStreamingMessage(): void {
  if (streamingEl) {
    streamingEl.classList.remove("streaming");
    streamingEl = null;
  }
}
