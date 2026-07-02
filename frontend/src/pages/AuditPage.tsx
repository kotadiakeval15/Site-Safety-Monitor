import { useEffect, useState } from "react";
import { api } from "../services/api";
import type { AuditLog } from "../types";
import { Badge, Card, EmptyRow, Loading, formatDate } from "../components/ui";

export default function AuditPage() {
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.listAudit().then(setLogs).finally(() => setLoading(false));
  }, []);

  if (loading) return <Loading />;

  return (
    <>
      <div className="page-header">
        <div>
          <h2>Audit Log</h2>
          <p>Immutable history of privileged actions.</p>
        </div>
      </div>

      <Card bodyClass="">
        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr>
                <th>Action</th>
                <th>Details</th>
                <th>Time</th>
              </tr>
            </thead>
            <tbody>
              {logs.length === 0 && <EmptyRow colSpan={3} label="No audit records." />}
              {logs.map((log) => (
                <tr key={log.log_id}>
                  <td><Badge variant="primary">{log.action}</Badge></td>
                  <td className="mono helper-text truncate" style={{ maxWidth: 480 }}>
                    {log.details ? JSON.stringify(log.details) : "—"}
                  </td>
                  <td className="mono helper-text">{formatDate(log.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </>
  );
}
