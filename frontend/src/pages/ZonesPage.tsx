import { useEffect, useMemo, useRef, useState } from "react";
import { Pencil, Plus, Trash2 } from "lucide-react";
import { api, ApiError } from "../services/api";
import type { Camera, Zone, ZoneSeverity } from "../types";
import { Card, EmptyRow, Loading, Modal, SeverityBadge } from "../components/ui";
import { useAuth } from "../context/AuthContext";

const SEVERITIES: { value: ZoneSeverity; label: string; color: string }[] = [
  { value: "level_1", label: "Level 1 (Green)", color: "#16a34a" },
  { value: "level_2", label: "Level 2 (Yellow)", color: "#d97706" },
  { value: "danger", label: "Danger (Red)", color: "#dc2626" },
];

interface Segment {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
}

interface ZoneForm extends Segment {
  name: string;
  description: string;
  camera_id: string;
  severity: ZoneSeverity;
  is_active: boolean;
}

const DEFAULT_SEGMENT: Segment = { x1: 0.1, y1: 0.6, x2: 0.9, y2: 0.6 };

const EMPTY: ZoneForm = {
  name: "",
  description: "",
  camera_id: "",
  severity: "danger",
  is_active: true,
  ...DEFAULT_SEGMENT,
};

const clamp01 = (n: number) => Math.min(1, Math.max(0, n));

function segmentOf(zone: Zone): Segment {
  if (
    zone.line_x1 != null &&
    zone.line_y1 != null &&
    zone.line_x2 != null &&
    zone.line_y2 != null
  ) {
    return { x1: zone.line_x1, y1: zone.line_y1, x2: zone.line_x2, y2: zone.line_y2 };
  }
  return { x1: 0, y1: zone.line_y, x2: 1, y2: zone.line_y };
}

type Backdrop =
  | { kind: "live"; url: string }
  | { kind: "video"; url: string }
  | { kind: "none" };

export default function ZonesPage() {
  const { hasRole } = useAuth();
  const canManage = hasRole("admin");
  const [zones, setZones] = useState<Zone[]>([]);
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<Zone | null>(null);
  const [showModal, setShowModal] = useState(false);
  const [form, setForm] = useState<ZoneForm>(EMPTY);
  const [error, setError] = useState<string | null>(null);
  const [frameTick, setFrameTick] = useState(0);

  const cameraName = useMemo(
    () => Object.fromEntries(cameras.map((c) => [c.camera_id, c.name])),
    [cameras],
  );

  const load = async () => {
    const [z, c] = await Promise.all([api.listZones(), api.listCameras()]);
    setZones(z);
    setCameras(c);
    setLoading(false);
  };

  useEffect(() => {
    load();
  }, []);

  const activeCamera = useMemo(
    () => cameras.find((c) => c.camera_id === form.camera_id),
    [cameras, form.camera_id],
  );

  const backdrop: Backdrop = useMemo(() => {
    if (!activeCamera) return { kind: "none" };
    if (activeCamera.status === "active") {
      return { kind: "live", url: `${api.liveFrameUrl(activeCamera.camera_id)}&t=${frameTick}` };
    }
    if (activeCamera.source_type === "file" && activeCamera.has_video) {
      return { kind: "video", url: api.cameraVideoUrl(activeCamera.camera_id) };
    }
    return { kind: "none" };
  }, [activeCamera, frameTick]);

  useEffect(() => {
    if (!showModal || activeCamera?.status !== "active") return;
    const id = window.setInterval(() => setFrameTick(Date.now()), 1500);
    return () => window.clearInterval(id);
  }, [showModal, activeCamera?.status, activeCamera?.camera_id]);

  const openCreate = () => {
    setEditing(null);
    setForm({ ...EMPTY, camera_id: cameras[0]?.camera_id ?? "" });
    setError(null);
    setFrameTick(Date.now());
    setShowModal(true);
  };

  const openEdit = (zone: Zone) => {
    setEditing(zone);
    setForm({
      name: zone.name,
      description: zone.description ?? "",
      camera_id: zone.camera_id,
      severity: zone.severity,
      is_active: zone.is_active,
      ...segmentOf(zone),
    });
    setError(null);
    setFrameTick(Date.now());
    setShowModal(true);
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    const body = {
      name: form.name,
      description: form.description,
      severity: form.severity,
      is_active: form.is_active,
      line_x1: form.x1,
      line_y1: form.y1,
      line_x2: form.x2,
      line_y2: form.y2,
      line_y: (form.y1 + form.y2) / 2,
    };
    try {
      if (editing) {
        await api.updateZone(editing.zone_id, body);
      } else {
        await api.createZone({ ...body, camera_id: form.camera_id });
      }
      setShowModal(false);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to save zone");
    }
  };

  const remove = async (zone: Zone) => {
    if (!confirm(`Delete zone "${zone.name}"?`)) return;
    await api.deleteZone(zone.zone_id);
    await load();
  };

  if (loading) return <Loading />;

  const severityColor = SEVERITIES.find((s) => s.value === form.severity)?.color ?? "#dc2626";

  return (
    <>
      <div className="page-header">
        <div>
          <h2>Safety Zones</h2>
          <p>Draw a severity line on the floor. A worker whose foot crosses it raises a detection.</p>
        </div>
        {canManage && (
          <button className="btn btn-primary" onClick={openCreate} disabled={cameras.length === 0}>
            <Plus size={16} /> Add Zone
          </button>
        )}
      </div>

      {cameras.length === 0 && (
        <div className="error-text">Create a camera first before defining zones.</div>
      )}

      <Card bodyClass="">
        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr>
                <th>Name</th>
                <th>Camera</th>
                <th>Severity</th>
                <th>Line</th>
                <th>Active</th>
                {canManage && <th style={{ textAlign: "right" }}>Actions</th>}
              </tr>
            </thead>
            <tbody>
              {zones.length === 0 && <EmptyRow colSpan={canManage ? 6 : 5} label="No zones defined." />}
              {zones.map((z) => (
                <tr key={z.zone_id}>
                  <td style={{ fontWeight: 600 }}>{z.name}</td>
                  <td className="helper-text">{cameraName[z.camera_id] ?? "—"}</td>
                  <td>
                    <SeverityBadge value={z.severity} />
                  </td>
                  <td className="helper-text">Hand-drawn floor segment</td>
                  <td>
                    <span className="badge badge-neutral">
                      <span className={`dot ${z.is_active ? "dot-success" : "dot-muted"}`} />
                      {z.is_active ? "Active" : "Disabled"}
                    </span>
                  </td>
                  {canManage && (
                    <td>
                      <div className="toolbar" style={{ justifyContent: "flex-end" }}>
                        <button className="btn btn-ghost btn-sm" onClick={() => openEdit(z)}>
                          <Pencil size={14} />
                        </button>
                        <button className="btn btn-ghost btn-sm" onClick={() => remove(z)}>
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {showModal && (
        <Modal
          title={editing ? "Edit Zone" : "Add Zone"}
          onClose={() => setShowModal(false)}
          footer={
            <>
              <button className="btn btn-ghost" onClick={() => setShowModal(false)}>
                Cancel
              </button>
              <button className="btn btn-primary" form="zone-form">
                {editing ? "Save" : "Create"}
              </button>
            </>
          }
        >
          {error && <div className="error-text">{error}</div>}
          <form id="zone-form" onSubmit={submit}>
            <div className="field">
              <label>Name</label>
              <input
                className="input"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                required
              />
            </div>
            {!editing && (
              <div className="field">
                <label>Camera</label>
                <select
                  className="select"
                  value={form.camera_id}
                  onChange={(e) => {
                    setForm({ ...form, camera_id: e.target.value });
                    setFrameTick(Date.now());
                  }}
                  required
                >
                  {cameras.map((c) => (
                    <option key={c.camera_id} value={c.camera_id}>
                      {c.name}
                    </option>
                  ))}
                </select>
              </div>
            )}
            <div className="field">
              <label>Severity</label>
              <select
                className="select"
                value={form.severity}
                onChange={(e) => setForm({ ...form, severity: e.target.value as ZoneSeverity })}
              >
                {SEVERITIES.map((s) => (
                  <option key={s.value} value={s.value}>
                    {s.label}
                  </option>
                ))}
              </select>
            </div>

            <div className="field">
              <label>Line on floor — drag the two handles</label>
              <LineEditor
                value={form}
                color={severityColor}
                backdrop={backdrop}
                onChange={(seg) => setForm({ ...form, ...seg })}
              />
              <div className="toolbar" style={{ marginTop: 8 }}>
                <button
                  type="button"
                  className="btn btn-ghost btn-sm"
                  onClick={() => setForm({ ...form, ...DEFAULT_SEGMENT })}
                >
                  Reset to horizontal
                </button>
                <span className="helper-text">
                  {backdrop.kind === "live"
                    ? "Live camera frame — align the line to the floor."
                    : backdrop.kind === "video"
                      ? "Uploaded video frame — align the line to the floor."
                      : "Activate the camera or upload a video to see a frame guide."}
                </span>
              </div>
            </div>

            <div className="field">
              <label>Description</label>
              <textarea
                className="input"
                rows={2}
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
              />
            </div>
            <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: "0.88rem" }}>
              <input
                type="checkbox"
                checked={form.is_active}
                onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
              />
              Zone active
            </label>
          </form>
        </Modal>
      )}
    </>
  );
}

function LineEditor({
  value,
  color,
  backdrop,
  onChange,
}: {
  value: Segment;
  color: string;
  backdrop: Backdrop;
  onChange: (seg: Segment) => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [drag, setDrag] = useState<null | "p1" | "p2">(null);

  const pointToNorm = (clientX: number, clientY: number): { x: number; y: number } => {
    const rect = ref.current?.getBoundingClientRect();
    if (!rect) return { x: 0, y: 0 };
    return {
      x: clamp01((clientX - rect.left) / rect.width),
      y: clamp01((clientY - rect.top) / rect.height),
    };
  };

  const onMove = (e: React.PointerEvent) => {
    if (!drag) return;
    const { x, y } = pointToNorm(e.clientX, e.clientY);
    onChange(drag === "p1" ? { ...value, x1: x, y1: y } : { ...value, x2: x, y2: y });
  };

  const startDrag = (which: "p1" | "p2") => (e: React.PointerEvent<HTMLDivElement>) => {
    e.currentTarget.setPointerCapture(e.pointerId);
    setDrag(which);
  };

  const endDrag = (e: React.PointerEvent<HTMLDivElement>) => {
    if (e.currentTarget.hasPointerCapture(e.pointerId)) {
      e.currentTarget.releasePointerCapture(e.pointerId);
    }
    setDrag(null);
  };

  const handleStyle = (nx: number, ny: number): React.CSSProperties => ({
    position: "absolute",
    left: `${nx * 100}%`,
    top: `${ny * 100}%`,
    width: 18,
    height: 18,
    marginLeft: -9,
    marginTop: -9,
    borderRadius: "50%",
    background: color,
    border: "2px solid #fff",
    boxShadow: "0 0 0 1px rgba(0,0,0,0.45)",
    cursor: drag ? "grabbing" : "grab",
    touchAction: "none",
    zIndex: 2,
  });

  return (
    <div
      ref={ref}
      onPointerMove={onMove}
      onPointerUp={endDrag}
      onPointerCancel={endDrag}
      style={{
        position: "relative",
        width: "100%",
        aspectRatio: "16 / 9",
        background: "var(--surface-2)",
        border: "1px solid var(--border)",
        borderRadius: 8,
        overflow: "hidden",
        userSelect: "none",
      }}
    >
      {backdrop.kind === "live" && (
        <img
          src={backdrop.url}
          alt="Live camera frame"
          draggable={false}
          onError={(e) => {
            (e.currentTarget as HTMLImageElement).style.display = "none";
          }}
          style={{ position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: "fill" }}
        />
      )}
      {backdrop.kind === "video" && (
        <video
          src={backdrop.url}
          muted
          playsInline
          preload="metadata"
          draggable={false}
          onLoadedData={(e) => {
            e.currentTarget.currentTime = 0.1;
          }}
          style={{ position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: "fill" }}
        />
      )}
      <svg
        viewBox="0 0 100 100"
        preserveAspectRatio="none"
        style={{ position: "absolute", inset: 0, width: "100%", height: "100%", pointerEvents: "none" }}
      >
        <line
          x1={value.x1 * 100}
          y1={value.y1 * 100}
          x2={value.x2 * 100}
          y2={value.y2 * 100}
          stroke={color}
          strokeWidth={0.9}
        />
      </svg>
      <div
        role="button"
        aria-label="Line start"
        style={handleStyle(value.x1, value.y1)}
        onPointerDown={startDrag("p1")}
      />
      <div
        role="button"
        aria-label="Line end"
        style={handleStyle(value.x2, value.y2)}
        onPointerDown={startDrag("p2")}
      />
    </div>
  );
}
