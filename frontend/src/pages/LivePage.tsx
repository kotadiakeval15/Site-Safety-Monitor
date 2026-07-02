import { useEffect, useMemo, useState } from "react";
import { VideoOff } from "lucide-react";
import { api, ApiError } from "../services/api";
import type { Camera, DetectionMode } from "../types";
import { Card, Loading, SeverityBadge, formatDate } from "../components/ui";
import { useAuth } from "../context/AuthContext";
import { useAlertsSocket, type LiveAlert } from "../hooks/useAlertsSocket";

const MODE_LABELS: Record<DetectionMode, string> = {
  restricted_area: "Restricted Area Entry",
  helmet: "Helmet Detection",
};

export default function LivePage() {
  const { hasRole } = useAuth();
  const canManage = hasRole("admin");
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [selected, setSelected] = useState<string>("");
  const [tick, setTick] = useState(Date.now());
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [events, setEvents] = useState<LiveAlert[]>([]);

  useEffect(() => {
    api.listCameras().then((cams) => {
      setCameras(cams);
      const active = cams.find((c) => c.status === "active") ?? cams[0];
      if (active) setSelected(active.camera_id);
      setLoading(false);
    });
  }, []);

  useAlertsSocket((event) => {
    if (event.type !== "alert") return;
    setEvents((prev) => [event, ...prev].slice(0, 40));
  });

  const current = useMemo(
    () => cameras.find((c) => c.camera_id === selected),
    [cameras, selected],
  );

  const changeMode = async (mode: DetectionMode) => {
    if (!current || mode === current.detection_mode) return;
    setBusy(true);
    setError(null);
    try {
      await api.updateCamera(current.camera_id, { detection_mode: mode });
      // Re-apply on a running worker so the new use-case takes effect.
      if (current.status === "active") {
        await api.deactivateCamera(current.camera_id);
        await api.activateCamera(current.camera_id);
      }
      setCameras(await api.listCameras());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to change detection mode");
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    if (current?.status !== "active") return;
    const id = setInterval(() => setTick(Date.now()), 500);
    return () => clearInterval(id);
  }, [current?.status, selected]);

  if (loading) return <Loading />;

  const frameUrl =
    current && current.status === "active"
      ? `${api.liveFrameUrl(current.camera_id)}&t=${tick}`
      : null;

  const cameraEvents = events.filter((e) => !current || e.camera_id === current.camera_id);

  return (
    <>
      <div className="page-header">
        <div>
          <h2>Live Detection</h2>
          <p>Annotated feed and real-time detection events.</p>
        </div>
        <div className="toolbar" style={{ flexWrap: "wrap" }}>
          <select
            className="select"
            style={{ maxWidth: 240 }}
            value={selected}
            onChange={(e) => setSelected(e.target.value)}
          >
            {cameras.length === 0 && <option value="">No cameras</option>}
            {cameras.map((c) => (
              <option key={c.camera_id} value={c.camera_id}>
                {c.name} {c.status === "active" ? "(live)" : `(${c.status})`}
              </option>
            ))}
          </select>
          {current && (
            <select
              className="select"
              style={{ maxWidth: 240 }}
              value={current.detection_mode}
              disabled={!canManage || busy}
              title="Choose what this camera detects"
              onChange={(e) => changeMode(e.target.value as DetectionMode)}
            >
              <option value="restricted_area">{MODE_LABELS.restricted_area}</option>
              <option value="helmet">{MODE_LABELS.helmet}</option>
            </select>
          )}
        </div>
      </div>

      {error && <div className="error-text">{error}</div>}
      {current?.detection_mode === "restricted_area" && current.zones.length === 0 && (
        <div className="error-text">
          No safety zones defined for this camera. Add zones so restricted-area lines appear.
        </div>
      )}

      <div className="live-grid">
        <Card title={current?.name ?? "Camera Feed"} bodyClass="card__body">
          {frameUrl ? (
            <img className="live-feed" src={frameUrl} alt="Live annotated feed" />
          ) : (
            <div className="live-placeholder">
              <div style={{ display: "grid", gap: 10, justifyItems: "center" }}>
                <VideoOff size={34} />
                <span>{current ? "Camera is not active. Activate it to start detection." : "Select a camera."}</span>
              </div>
            </div>
          )}
        </Card>

        <Card title="Live Events" bodyClass="card__body">
          <div className="event-feed">
            {cameraEvents.length === 0 && <p className="helper-text">Waiting for detections...</p>}
            {cameraEvents.map((e, i) => (
              <div className="event-item" key={`${e.alert_id}-${i}`}>
                <span
                  className="event-item__bar"
                  style={{
                    background:
                      e.level === "danger" ? "var(--danger)" : e.level === "level_2" ? "var(--warning)" : "var(--success)",
                  }}
                />
                <div style={{ flex: 1 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
                    <strong style={{ fontSize: "0.85rem" }}>{e.violation_type.replace("_", " ")}</strong>
                    <SeverityBadge value={e.level} />
                  </div>
                  <div className="helper-text" style={{ fontSize: "0.8rem" }}>{e.message}</div>
                  <div className="helper-text mono" style={{ fontSize: "0.72rem" }}>{formatDate(e.timestamp)}</div>
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </>
  );
}
