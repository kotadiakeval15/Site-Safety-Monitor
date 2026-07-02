import { useEffect, useRef, useState } from "react";
import {
  alertsSocketHub,
  type LiveAlert,
  type SocketEvent,
} from "../services/alertsSocket";
import { playCriticalBeep, playWarningBeep } from "../services/buzzer";

export type { LiveAlert, SocketEvent };

/** Subscribe to live alert WebSocket events. Returns connection status. */
export function useAlertsSocket(onEvent?: (event: SocketEvent) => void) {
  const [connected, setConnected] = useState(alertsSocketHub.connected);
  const [latest, setLatest] = useState<LiveAlert | null>(null);
  const handlerRef = useRef(onEvent);
  handlerRef.current = onEvent;

  useEffect(() => {
    const unsubEvents = alertsSocketHub.subscribe((event) => {
      if (event.type === "alert") setLatest(event);
      handlerRef.current?.(event);
    });
    const unsubConn = alertsSocketHub.onConnectionChange(setConnected);
    return () => {
      unsubEvents();
      unsubConn();
    };
  }, []);

  return { connected, latest };
}

/** Red restricted-area buzz duration (auto-stop; not tied to alert acknowledgement). */
const RED_BUZZ_DURATION_MS = 12_000;

/** Drive warning/critical buzzer behaviour from live WebSocket events. */
export function useAlertBuzzer(): void {
  const redBuzzIntervalRef = useRef<number | null>(null);
  const redBuzzStopRef = useRef<number | null>(null);

  const stopRedBuzz = () => {
    if (redBuzzIntervalRef.current !== null) {
      window.clearInterval(redBuzzIntervalRef.current);
      redBuzzIntervalRef.current = null;
    }
    if (redBuzzStopRef.current !== null) {
      window.clearTimeout(redBuzzStopRef.current);
      redBuzzStopRef.current = null;
    }
  };

  const startRedBuzz = (durationMs = RED_BUZZ_DURATION_MS) => {
    stopRedBuzz();
    playCriticalBeep();
    redBuzzIntervalRef.current = window.setInterval(() => playCriticalBeep(), 650);
    redBuzzStopRef.current = window.setTimeout(() => stopRedBuzz(), durationMs);
  };

  useEffect(() => {
    const unsub = alertsSocketHub.subscribe((event) => {
      if (event.type !== "alert") return;
      if (event.violation_type === "line_crossing" && event.crossed_line === "yellow") {
        playWarningBeep();
        return;
      }
      if (event.violation_type === "line_crossing" && event.crossed_line === "red") {
        startRedBuzz();
      }
    });
    return () => {
      unsub();
      stopRedBuzz();
    };
  }, []);
}
