import { useEffect, useMemo, useState } from "react";
import { api } from "../services/api";
import type { Camera, Detection, ViolationType } from "../types";
import { Badge, Card, EmptyRow, Loading, Pagination, SeverityBadge, formatDate } from "../components/ui";

export default function DetectionsPage() {
  const [detections, setDetections] = useState<Detection[]>([]);
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalItems, setTotalItems] = useState(0);
  const [cameraId, setCameraId] = useState("");
  const [violationType, setViolationType] = useState<ViolationType | "">("");

  const cameraName = useMemo(
    () => Object.fromEntries(cameras.map((c) => [c.camera_id, c.name])),
    [cameras],
  );

  useEffect(() => {
    api.listCameras().then(setCameras);
  }, []);

  useEffect(() => {
    setLoading(true);
    api
      .listDetections({
        page,
        page_size: 15,
        camera_id: cameraId || undefined,
        violation_type: violationType || undefined,
      })
      .then((res) => {
        setDetections(res.items);
        setTotalPages(res.pagination.total_pages);
        setTotalItems(res.pagination.total_items);
      })
      .finally(() => setLoading(false));
  }, [page, cameraId, violationType]);

  return (
    <>
      <div className="page-header">
        <div>
          <h2>Detections</h2>
          <p>All recorded helmet violations and line crossings.</p>
        </div>
        <div className="toolbar">
          <select
            className="select"
            value={cameraId}
            onChange={(e) => {
              setPage(1);
              setCameraId(e.target.value);
            }}
          >
            <option value="">All cameras</option>
            {cameras.map((c) => (
              <option key={c.camera_id} value={c.camera_id}>
                {c.name}
              </option>
            ))}
          </select>
          <select
            className="select"
            value={violationType}
            onChange={(e) => {
              setPage(1);
              setViolationType(e.target.value as ViolationType | "");
            }}
          >
            <option value="">All types</option>
            <option value="helmet_violation">Helmet Violation</option>
            <option value="line_crossing">Line Crossing</option>
          </select>
        </div>
      </div>

      <Card bodyClass="">
        {loading ? (
          <Loading />
        ) : (
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>Type</th>
                  <th>Camera</th>
                  <th>Worker</th>
                  <th>Severity</th>
                  <th>Line</th>
                  <th>Confidence</th>
                  <th>Time</th>
                </tr>
              </thead>
              <tbody>
                {detections.length === 0 && <EmptyRow colSpan={7} label="No detections found." />}
                {detections.map((d) => (
                  <tr key={d.detection_id}>
                    <td>
                      <Badge variant={d.violation_type === "helmet_violation" ? "danger" : "primary"}>
                        {d.violation_type.replace("_", " ")}
                      </Badge>
                    </td>
                    <td className="helper-text">{cameraName[d.camera_id] ?? "—"}</td>
                    <td className="mono">#{d.worker_id}</td>
                    <td>
                      <SeverityBadge value={d.severity} />
                    </td>
                    <td>{d.crossed_line ? <Badge variant="neutral">{d.crossed_line}</Badge> : "—"}</td>
                    <td className="mono">{(d.confidence * 100).toFixed(0)}%</td>
                    <td className="mono helper-text">{formatDate(d.created_at)}</td>
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
