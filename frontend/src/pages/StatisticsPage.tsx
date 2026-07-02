import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Activity, AlertTriangle, Video } from "lucide-react";
import { api } from "../services/api";
import type { DetectionStatistics } from "../types";
import { Card, Loading, StatCard } from "../components/ui";

const SEVERITY_COLORS: Record<string, string> = {
  level_1: "#16a34a",
  level_2: "#d97706",
  danger: "#dc2626",
};
const TYPE_COLORS = ["#2563eb", "#7c3aed", "#0891b2", "#db2777"];

const WINDOWS = [
  { label: "24 hours", value: 24 },
  { label: "7 days", value: 168 },
  { label: "30 days", value: 720 },
];

export default function StatisticsPage() {
  const [stats, setStats] = useState<DetectionStatistics | null>(null);
  const [windowHours, setWindowHours] = useState(24);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api
      .statistics(windowHours)
      .then(setStats)
      .finally(() => setLoading(false));
  }, [windowHours]);

  if (loading || !stats) return <Loading />;
  const s = stats.summary;

  const timeData = stats.over_time.map((t) => ({
    time: new Date(t.bucket).toLocaleString(undefined, {
      month: "short",
      day: "2-digit",
      hour: "2-digit",
    }),
    count: t.count,
  }));

  return (
    <>
      <div className="page-header">
        <div>
          <h2>Detection Statistics</h2>
          <p>Aggregated analytics across cameras, zones and violation types.</p>
        </div>
        <select
          className="select"
          style={{ maxWidth: 180 }}
          value={windowHours}
          onChange={(e) => setWindowHours(Number(e.target.value))}
        >
          {WINDOWS.map((w) => (
            <option key={w.value} value={w.value}>
              Last {w.label}
            </option>
          ))}
        </select>
      </div>

      <div className="grid grid-kpi" style={{ marginBottom: 20 }}>
        <StatCard label="Total Detections" value={s.total_detections} icon={<Activity size={20} />} tone="primary" />
        <StatCard label="Detections Today" value={s.detections_today} icon={<Activity size={20} />} tone="warning" />
        <StatCard
          label="Unacknowledged"
          value={s.unacknowledged_alerts}
          icon={<AlertTriangle size={20} />}
          tone="danger"
        />
        <StatCard
          label="Active Cameras"
          value={`${s.active_cameras}/${s.total_cameras}`}
          icon={<Video size={20} />}
          tone="success"
        />
      </div>

      <div className="grid grid-2" style={{ marginBottom: 20 }}>
        <Card title="Violations Over Time">
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={timeData}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="time" tick={{ fontSize: 11, fill: "var(--text-muted)" }} />
              <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: "var(--text-muted)" }} />
              <Tooltip
                contentStyle={{
                  background: "var(--surface)",
                  border: "1px solid var(--border)",
                  borderRadius: 8,
                }}
              />
              <Line type="monotone" dataKey="count" stroke="#2563eb" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </Card>

        <Card title="By Violation Type">
          {stats.by_type.length === 0 ? (
            <p className="helper-text">No data for this window.</p>
          ) : (
            <ResponsiveContainer width="100%" height={280}>
              <PieChart>
                <Pie data={stats.by_type} dataKey="count" nameKey="label" outerRadius={100} label>
                  {stats.by_type.map((_, i) => (
                    <Cell key={i} fill={TYPE_COLORS[i % TYPE_COLORS.length]} />
                  ))}
                </Pie>
                <Legend />
                <Tooltip
                  contentStyle={{
                    background: "var(--surface)",
                    border: "1px solid var(--border)",
                    borderRadius: 8,
                  }}
                />
              </PieChart>
            </ResponsiveContainer>
          )}
        </Card>
      </div>

      <div className="grid grid-2">
        <Card title="By Camera">
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={stats.by_camera.map((c) => ({ name: c.camera_name, count: c.count }))}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="name" tick={{ fontSize: 11, fill: "var(--text-muted)" }} />
              <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: "var(--text-muted)" }} />
              <Tooltip
                contentStyle={{
                  background: "var(--surface)",
                  border: "1px solid var(--border)",
                  borderRadius: 8,
                }}
                cursor={{ fill: "var(--surface-hover)" }}
              />
              <Bar dataKey="count" fill="#7c3aed" radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Card>

        <Card title="By Severity">
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={stats.by_severity.map((b) => ({ ...b }))}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="label" tick={{ fontSize: 11, fill: "var(--text-muted)" }} />
              <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: "var(--text-muted)" }} />
              <Tooltip
                contentStyle={{
                  background: "var(--surface)",
                  border: "1px solid var(--border)",
                  borderRadius: 8,
                }}
                cursor={{ fill: "var(--surface-hover)" }}
              />
              <Bar dataKey="count" radius={[6, 6, 0, 0]}>
                {stats.by_severity.map((b, i) => (
                  <Cell key={i} fill={SEVERITY_COLORS[b.key] ?? "#2563eb"} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Card>
      </div>
    </>
  );
}
