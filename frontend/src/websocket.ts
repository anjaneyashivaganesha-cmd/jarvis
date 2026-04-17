export type MessageHandler = (data: Record<string, unknown>) => void;

export class JarvisSocket {
  private ws: WebSocket | null = null;
  private handlers: Map<string, MessageHandler[]> = new Map();
  private url: string;
  private messageQueue: Record<string, unknown>[] = [];
  private reconnectDelay = 1000;
  private lastPongAt = Date.now();
  private pongCheckInterval: number | null = null;

  constructor(url = "ws://localhost:8000/ws") {
    this.url = url;
  }

  connect(): void {
    try {
      this.ws = new WebSocket(this.url);
    } catch (e) {
      console.error("[ws] Failed to create WebSocket:", e);
      this.scheduleReconnect();
      return;
    }

    this.ws.onopen = () => {
      console.log("[ws] connected");
      this.reconnectDelay = 1000; // reset backoff on success
      this.lastPongAt = Date.now();
      this.emit("connected", {});
      this.flushQueue();
      this.startPongCheck();
    };

    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === "pong") {
          this.lastPongAt = Date.now();
        }
        this.emit(data.type, data);
      } catch (e) {
        console.error("[ws] Failed to parse message:", e);
      }
    };

    this.ws.onclose = () => {
      console.log("[ws] disconnected");
      this.stopPongCheck();
      this.emit("disconnected", {});
      this.scheduleReconnect();
    };

    this.ws.onerror = (err) => {
      console.error("[ws] error", err);
    };
  }

  private scheduleReconnect(): void {
    // Exponential backoff: 1s, 2s, 4s, max 8s
    const delay = this.reconnectDelay;
    this.reconnectDelay = Math.min(this.reconnectDelay * 2, 8000);
    console.log(`[ws] reconnecting in ${delay}ms...`);
    setTimeout(() => this.connect(), delay);
  }

  private flushQueue(): void {
    while (this.messageQueue.length > 0) {
      const msg = this.messageQueue.shift()!;
      console.log("[ws] flushing queued message:", msg.type);
      this.send(msg);
    }
  }

  private startPongCheck(): void {
    this.stopPongCheck();
    // Check every 20s if we've received a pong recently
    this.pongCheckInterval = window.setInterval(() => {
      const silentFor = Date.now() - this.lastPongAt;
      if (silentFor > 30000 && this.ws?.readyState === WebSocket.OPEN) {
        console.warn("[ws] No pong for 30s — connection stale, forcing reconnect");
        this.ws.close();
      }
    }, 20000);
  }

  private stopPongCheck(): void {
    if (this.pongCheckInterval) {
      clearInterval(this.pongCheckInterval);
      this.pongCheckInterval = null;
    }
  }

  send(data: Record<string, unknown>): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
    } else if (data.type === "transcript") {
      // Queue important messages (commands) during disconnect — drop pings
      console.warn("[ws] Not connected, queuing command");
      this.messageQueue.push(data);
    }
  }

  isConnected(): boolean {
    return this.ws !== null && this.ws.readyState === WebSocket.OPEN;
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
