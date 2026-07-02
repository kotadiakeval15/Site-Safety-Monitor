import { getWsUrl } from "./api";

export interface LiveAlert {
  type: "alert";
  alert_id: string;
  detection_id?: string;
  camera_id: string;
  worker_id: number;
  violation_type: string;
  severity: string;
  level: string;
  crossed_line?: string | null;
  message?: string | null;
  timestamp: string;
}

export interface ZoneExitEvent {
  type: "zone_exit";
  camera_id: string;
  worker_id: number;
  crossed_line?: string | null;
  message?: string | null;
}

export interface AlertAckEvent {
  type: "alert_acknowledged";
  alert_id: string;
  acknowledged: boolean;
}

export type SocketEvent = LiveAlert | ZoneExitEvent | AlertAckEvent;

type Listener = (event: SocketEvent) => void;
type ConnectionListener = (connected: boolean) => void;

class AlertsSocketHub {
  private ws: WebSocket | null = null;
  private closed = false;
  private retryMs = 1000;
  private retryTimer: number | null = null;
  private listeners = new Set<Listener>();
  private connectionListeners = new Set<ConnectionListener>();
  connected = false;

  subscribe(listener: Listener): () => void {
    this.listeners.add(listener);
    this.ensureConnected();
    return () => this.listeners.delete(listener);
  }

  onConnectionChange(listener: ConnectionListener): () => void {
    this.connectionListeners.add(listener);
    listener(this.connected);
    this.ensureConnected();
    return () => this.connectionListeners.delete(listener);
  }

  private ensureConnected(): void {
    if (this.ws || this.closed) return;
    this.connect();
  }

  private setConnected(value: boolean): void {
    this.connected = value;
    this.connectionListeners.forEach((listener) => listener(value));
  }

  private connect(): void {
    if (this.closed) return;
    this.ws = new WebSocket(getWsUrl());
    this.ws.onopen = () => {
      this.retryMs = 1000;
      this.setConnected(true);
    };
    this.ws.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data as string) as SocketEvent;
        this.listeners.forEach((listener) => listener(payload));
      } catch {
        /* ignore malformed payloads */
      }
    };
    this.ws.onclose = () => {
      this.ws = null;
      this.setConnected(false);
      if (!this.closed) {
        this.retryTimer = window.setTimeout(() => {
          this.retryMs = Math.min(this.retryMs * 2, 15000);
          this.connect();
        }, this.retryMs);
      }
    };
  }

  close(): void {
    this.closed = true;
    if (this.retryTimer !== null) window.clearTimeout(this.retryTimer);
    this.ws?.close();
    this.ws = null;
  }
}

export const alertsSocketHub = new AlertsSocketHub();
