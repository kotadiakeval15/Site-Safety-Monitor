import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Activity, AlertTriangle, Bell, Camera, ShieldAlert, Video } from "lucide-react";
import { api } from "../services/api";
import type { Alert, DetectionStatistics } from "../types";
import { Card, Loading, SeverityBadge, StatCard, formatDate } from "../components/ui";
import { useAlertsSocket } from "../hooks/useAlertsSocket";

export default function DashboardPage() {
  const [stats, setStats] = useState<DetectionStatistics | null>(null);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [health, setHealth] = useState<{ status: string; database: string } | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    const [s, a, h] = await Promise.all([
      api.statistics(24),
      api.listAlerts({ page: 1, page_size: 6, unacknowledged_only: true }),
      api.health().catch(() => null),
    ]);
    setStats(s);
    setAlerts(a.items);
    setHealth(h);
    setLoading(false);
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(load, 15000);
    return () => clearInterval(id);
  }, [load]);

  useAlertsSocket((event) => {
    if (event.type === "alert") load();
  });

  if (loading || !stats) return <Loading />;
  const s = stats.summary;

  return (
    <div style={{ display: "grid", gap: 20 }}>
      <div className="grid grid-kpi">
        <StatCard label="Active Cameras" value={`${s.active_cameras}/${s.total_cameras}`} icon={<Video size={20} />} tone="primary" />
        <StatCard label="Safety Zones" value={s.total_zones} icon={<ShieldAlert size={20} />} tone="primary" />
        <StatCard label="Detections Today" value={s.detections_today} icon={<Activity size={20} />} tone="warning" />
        <StatCard label="Total Detections" value={s.total_detections} icon={<Activity size={20} />} tone="primary" />
        <StatCard label="Unacknowledged Alerts" value={s.unacknowledged_alerts} icon={<Bell size={20} />} tone="danger" />
        <StatCard label="Total Alerts" value={s.total_alerts} icon={<AlertTriangle size={20} />} tone="warning" />
      </div>

      <div className="grid grid-2">
        <Card
          title="Active Alerts"
          actions={<Link className="btn btn-ghost btn-sm" to="/alerts">View all</Link>}
          bodyClass=""
        >
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>Level</th>
                  <th>Message</th>
                  <th>Time</th>
                </tr>
              </thead>
              <tbody>
                {alerts.length === 0 && (
                  <tr>
                    <td colSpan={3}>
                      <div className="table-empty">No active alerts. All clear.</div>
                    </td>
                  </tr>
                )}
                {alerts.map((a) => (
                  <tr key={a.alert_id}>
                    <td><SeverityBadge value={a.level} /></td>
                    <td className="truncate">{a.message ?? "—"}</td>
                    <td className="mono helper-text">{formatDate(a.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>

        <Card title="System Health">
          <div style={{ display: "grid", gap: 14 }}>
            <HealthRow label="Backend API" ok={true} value="Operational" />
            <HealthRow label="Database" ok={health?.database === "up"} value={health?.database ?? "unknown"} />
            <HealthRow
              label="Detection Camera Workers"
              ok={s.active_cameras > 0}
              value={`${s.active_cameras} running`}
            />
            <div style={{ marginTop: 6 }}>
              <Link className="btn btn-primary btn-sm" to="/cameras">
                <Camera size={15} /> Manage Cameras
              </Link>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}

function HealthRow({ label, ok, value }: { label: string; ok: boolean; value: string }) {
  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
      <span className="helper-text">{label}</span>
      <span className="badge badge-neutral">
        <span className={`dot ${ok ? "dot-success" : "dot-danger"}`} /> {value}
      </span>
    </div>
  );
}
