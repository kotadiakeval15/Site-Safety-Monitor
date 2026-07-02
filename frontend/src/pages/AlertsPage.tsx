import { useCallback, useEffect, useState } from "react";
import { Check, Undo2 } from "lucide-react";
import { api } from "../services/api";
import type { Alert } from "../types";
import { Card, EmptyRow, Loading, Pagination, SeverityBadge, formatDate } from "../components/ui";
import { useAuth } from "../context/AuthContext";
import { useAlertsSocket } from "../hooks/useAlertsSocket";

export default function AlertsPage() {
  const { hasRole } = useAuth();
  const canAck = hasRole("admin");
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalItems, setTotalItems] = useState(0);
  const [unackOnly, setUnackOnly] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    api
      .listAlerts({ page, page_size: 15, unacknowledged_only: unackOnly })
      .then((res) => {
        setAlerts(res.items);
        setTotalPages(res.pagination.total_pages);
        setTotalItems(res.pagination.total_items);
      })
      .finally(() => setLoading(false));
  }, [page, unackOnly]);

  useEffect(() => {
    load();
  }, [load]);

  useAlertsSocket((event) => {
    if (event.type === "alert" && page === 1) load();
  });

  const toggleAck = async (alert: Alert) => {
    await api.acknowledgeAlert(alert.alert_id, !alert.acknowledged);
    load();
  };

  return (
    <>
      <div className="page-header">
        <div>
          <h2>Alerts</h2>
          <p>Triage and acknowledge safety incidents.</p>
        </div>
        <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: "0.88rem" }}>
          <input
            type="checkbox"
            checked={unackOnly}
            onChange={(e) => { setPage(1); setUnackOnly(e.target.checked); }}
          />
          Unacknowledged only
        </label>
      </div>

      <Card bodyClass="">
        {loading ? (
          <Loading />
        ) : (
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>Level</th>
                  <th>Message</th>
                  <th>Status</th>
                  <th>Time</th>
                  {canAck && <th style={{ textAlign: "right" }}>Actions</th>}
                </tr>
              </thead>
              <tbody>
                {alerts.length === 0 && <EmptyRow colSpan={canAck ? 5 : 4} label="No alerts." />}
                {alerts.map((a) => (
                  <tr key={a.alert_id}>
                    <td><SeverityBadge value={a.level} /></td>
                    <td className="truncate">{a.message ?? "—"}</td>
                    <td>
                      <span className="badge badge-neutral">
                        <span className={`dot ${a.acknowledged ? "dot-success" : "dot-danger"}`} />
                        {a.acknowledged ? "Acknowledged" : "Open"}
                      </span>
                    </td>
                    <td className="mono helper-text">{formatDate(a.created_at)}</td>
                    {canAck && (
                      <td style={{ textAlign: "right" }}>
                        <button
                          className={`btn btn-sm ${a.acknowledged ? "btn-ghost" : "btn-success"}`}
                          onClick={() => toggleAck(a)}
                        >
                          {a.acknowledged ? <Undo2 size={14} /> : <Check size={14} />}
                          {a.acknowledged ? "Reopen" : "Acknowledge"}
                        </button>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <Pagination page={page} totalPages={totalPages} totalItems={totalItems} onChange={setPage} />
      </Card>
    </>
  );
}
