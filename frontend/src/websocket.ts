export type MessageHandler = (data: Record<string, unknown>) => void;

export class JarvisSocket {
  private ws: WebSocket | null = null;
  private handlers: Map<string, MessageHandler[]> = new Map();
  private url: string;

  constructor(url = "ws://localhost:8000/ws") {
    this.url = url;
  }

  connect(): void {
    this.ws = new WebSocket(this.url);

    this.ws.onopen = () => {
      console.log("[ws] connected");
      this.emit("connected", {});
    };

    this.ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      this.emit(data.type, data);
    };

    this.ws.onclose = () => {
      console.log("[ws] disconnected, reconnecting in 2s...");
      this.emit("disconnected", {});
      setTimeout(() => this.connect(), 2000);
    };

    this.ws.onerror = (err) => {
      console.error("[ws] error", err);
    };
  }

  send(data: Record<string, unknown>): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
    }
  }

  on(type: string, handler: MessageHandler): void {
    if (!this.handlers.has(type)) {
      this.handlers.set(type, []);
    }
    this.handlers.get(type)!.push(handler);
  }

  private emit(type: string, data: Record<string, unknown>): void {
    const handlers = this.handlers.get(type) || [];
    for (const h of handlers) h(data);
  }
}
