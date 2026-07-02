import { useEffect, useRef, useState } from "react";
import { Pause, Play, Plus, Trash2, Upload } from "lucide-react";
import { api, ApiError } from "../services/api";
import type { Camera, SourceType } from "../types";
import { Card, EmptyRow, Loading, Modal, StatusBadge } from "../components/ui";
import { useAuth } from "../context/AuthContext";

const SOURCE_TYPES: SourceType[] = ["file", "cctv", "ip", "webcam", "mobile"];

export default function CamerasPage() {
  const { hasRole } = useAuth();
  const canManage = hasRole("admin");
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [playing, setPlaying] = useState<Camera | null>(null);

  const [form, setForm] = useState({ name: "", source_type: "file" as SourceType, stream_url: "" });
  const [videoFile, setVideoFile] = useState<File | null>(null);
  const replaceInput = useRef<HTMLInputElement | null>(null);
  const [replaceTarget, setReplaceTarget] = useState<string | null>(null);

  const load = async () => {
    setCameras(await api.listCameras());
    setLoading(false);
  };

  useEffect(() => {
    load();
  }, []);

  const resetForm = () => {
    setForm({ name: "", source_type: "file", stream_url: "" });
    setVideoFile(null);
  };

  const create = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      if (form.source_type === "file") {
        if (!videoFile) {
          setError("Please choose a video file to upload.");
          return;
        }
        const cam = await api.createCamera({
          name: form.name,
          source_type: "file",
          stream_url: videoFile.name,
        });
        await api.uploadCameraVideo(cam.camera_id, videoFile);
      } else {
        if (!form.stream_url) {
          setError("A stream URL / source is required.");
          return;
        }
        await api.createCamera({
          name: form.name,
          source_type: form.source_type,
          stream_url: form.stream_url,
        });
      }
      setShowModal(false);
      resetForm();
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create camera");
    }
  };

  const toggle = async (cam: Camera) => {
    setBusy(cam.camera_id);
    setError(null);
    try {
      if (cam.status === "active") await api.deactivateCamera(cam.camera_id);
      else await api.activateCamera(cam.camera_id);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Action failed");
    } finally {
      setBusy(null);
    }
  };

  const remove = async (cam: Camera) => {
    if (!confirm(`Delete camera "${cam.name}"? This also removes its zones.`)) return;
    setBusy(cam.camera_id);
    try {
      await api.deleteCamera(cam.camera_id);
      await load();
    } finally {
      setBusy(null);
    }
  };

  const pickReplacement = (cameraId: string) => {
    setReplaceTarget(cameraId);
    replaceInput.current?.click();
  };

  const onReplaceSelected = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file || !replaceTarget) return;
    const cameraId = replaceTarget;
    setReplaceTarget(null);
    setBusy(cameraId);
    setError(null);
    try {
      await api.uploadCameraVideo(cameraId, file);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Upload failed");
    } finally {
      setBusy(null);
    }
  };

  if (loading) return <Loading />;

  return (
    <>
      <div className="page-header">
        <div>
          <h2>Cameras</h2>
          <p>Register camera sources and control their AI detection workers.</p>
        </div>
        {canManage && (
          <button
            className="btn btn-primary"
            onClick={() => {
              resetForm();
              setError(null);
              setShowModal(true);
            }}
          >
            <Plus size={16} /> Add Camera
          </button>
        )}
      </div>

      {error && <div className="error-text">{error}</div>}

      <input
        ref={replaceInput}
        type="file"
        accept="video/*"
        hidden
        onChange={onReplaceSelected}
      />

      <Card bodyClass="">
        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr>
                <th>Name</th>
                <th>Source</th>
                <th>Video / Source</th>
                <th>Zones</th>
                <th>Status</th>
                {canManage && <th style={{ textAlign: "right" }}>Actions</th>}
              </tr>
            </thead>
            <tbody>
              {cameras.length === 0 && <EmptyRow colSpan={canManage ? 6 : 5} label="No cameras yet." />}
              {cameras.map((cam) => (
                <tr key={cam.camera_id}>
                  <td style={{ fontWeight: 600 }}>{cam.name}</td>
                  <td><span className="badge badge-neutral">{cam.source_type}</span></td>
                  <td>
                    {cam.has_video ? (
                      <button className="btn btn-ghost btn-sm" onClick={() => setPlaying(cam)}>
                        <Play size={14} /> Play video
                      </button>
                    ) : cam.source_type === "file" ? (
                      <span className="helper-text">No video uploaded</span>
                    ) : (
                      <span className="truncate mono helper-text">{cam.stream_url}</span>
                    )}
                  </td>
                  <td>{cam.zones.length}</td>
                  <td><StatusBadge value={cam.status} /></td>
                  {canManage && (
                    <td>
                      <div className="toolbar" style={{ justifyContent: "flex-end" }}>
                        {cam.source_type === "file" && (
                          <button
                            className="btn btn-ghost btn-sm"
                            disabled={busy === cam.camera_id}
                            onClick={() => pickReplacement(cam.camera_id)}
                          >
                            <Upload size={14} /> {cam.has_video ? "Replace" : "Upload"}
                          </button>
                        )}
                        <button
                          className={`btn btn-sm ${cam.status === "active" ? "btn-ghost" : "btn-success"}`}
                          disabled={busy === cam.camera_id}
                          onClick={() => toggle(cam)}
                        >
                          {cam.status === "active" ? <Pause size={14} /> : <Play size={14} />}
                          {cam.status === "active" ? "Deactivate" : "Activate"}
                        </button>
                        <button
                          className="btn btn-ghost btn-sm"
                          disabled={busy === cam.camera_id}
                          onClick={() => remove(cam)}
                          aria-label="Delete camera"
                        >
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
          title="Add Camera"
          onClose={() => setShowModal(false)}
          footer={
            <>
              <button className="btn btn-ghost" onClick={() => setShowModal(false)}>Cancel</button>
              <button className="btn btn-primary" form="camera-form">Create</button>
            </>
          }
        >
          <form id="camera-form" onSubmit={create}>
            <div className="field">
              <label>Name</label>
              <input
                className="input"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="North Gate CCTV"
                required
              />
            </div>
            <div className="field">
              <label>Source Type</label>
              <select
                className="select"
                value={form.source_type}
                onChange={(e) => setForm({ ...form, source_type: e.target.value as SourceType })}
              >
                {SOURCE_TYPES.map((t) => (
                  <option key={t} value={t}>{t.toUpperCase()}</option>
                ))}
              </select>
            </div>
            {form.source_type === "file" ? (
              <div className="field">
                <label>Video File</label>
                <input
                  className="input"
                  type="file"
                  accept="video/*"
                  onChange={(e) => setVideoFile(e.target.files?.[0] ?? null)}
                  required
                />
                <span className="helper-text">
                  Upload a recorded video (mp4, mov, avi, mkv, webm). The AI worker runs on it.
                </span>
              </div>
            ) : (
              <div className="field">
                <label>Stream URL / Source</label>
                <input
                  className="input"
                  value={form.stream_url}
                  onChange={(e) => setForm({ ...form, stream_url: e.target.value })}
                  placeholder="rtsp://... | 0 (webcam index)"
                  required
                />
                <span className="helper-text">Use an RTSP URL or a webcam index (e.g. 0).</span>
              </div>
            )}
          </form>
        </Modal>
      )}

      {playing && (
        <Modal
          title={`${playing.name} — Uploaded Video`}
          onClose={() => setPlaying(null)}
          footer={<button className="btn btn-ghost" onClick={() => setPlaying(null)}>Close</button>}
        >
          <video
            controls
            autoPlay
            style={{ width: "100%", borderRadius: 8, background: "#000" }}
            src={api.cameraVideoUrl(playing.camera_id)}
          />
        </Modal>
      )}
    </>
  );
}
