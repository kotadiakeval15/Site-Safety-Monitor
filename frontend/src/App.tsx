import { Navigate, Route, Routes } from "react-router-dom";
import AlertBuzzer from "./components/AlertBuzzer";
import { Layout } from "./components/Layout";
import { ProtectedRoute } from "./components/ProtectedRoute";
import LoginPage from "./pages/LoginPage";
import DashboardPage from "./pages/DashboardPage";
import LivePage from "./pages/LivePage";
import CamerasPage from "./pages/CamerasPage";
import ZonesPage from "./pages/ZonesPage";
import DetectionsPage from "./pages/DetectionsPage";
import AlertsPage from "./pages/AlertsPage";
import StatisticsPage from "./pages/StatisticsPage";
import AuditPage from "./pages/AuditPage";

export default function App() {
  return (
    <>
      <AlertBuzzer />
      <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        element={
          <ProtectedRoute>
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/live" element={<LivePage />} />
        <Route path="/cameras" element={<CamerasPage />} />
        <Route path="/zones" element={<ZonesPage />} />
        <Route path="/detections" element={<DetectionsPage />} />
        <Route path="/alerts" element={<AlertsPage />} />
        <Route path="/statistics" element={<StatisticsPage />} />
        <Route path="/audit" element={<AuditPage />} />
      </Route>
      <Route path="/" element={<Navigate to="/dashboard" replace />} />
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </>
  );
}
