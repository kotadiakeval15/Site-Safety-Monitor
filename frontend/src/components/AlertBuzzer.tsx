import { useAlertBuzzer } from "../hooks/useAlertsSocket";

/** Mount once to handle browser buzzer alerts globally. */
export default function AlertBuzzer() {
  useAlertBuzzer();
  return null;
}
