const transcript = document.getElementById("transcript")!;
const status = document.getElementById("status")!;

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
