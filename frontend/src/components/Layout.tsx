import { useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import {
  Activity,
  BarChart3,
  Bell,
  Camera,
  HardHat,
  LayoutDashboard,
  LogOut,
  type LucideIcon,
  Menu,
  Moon,
  ScrollText,
  ShieldAlert,
  Sun,
  Video,
} from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { useTheme } from "../context/ThemeContext";
import { useAlertsSocket } from "../hooks/useAlertsSocket";

interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  minRole?: "admin" | "super_admin";
}

const NAV: NavItem[] = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/live", label: "Live Detection", icon: Video },
  { to: "/cameras", label: "Cameras", icon: Camera },
  { to: "/zones", label: "Safety Zones", icon: ShieldAlert },
  { to: "/detections", label: "Detections", icon: Activity },
  { to: "/alerts", label: "Alerts", icon: Bell },
  { to: "/statistics", label: "Statistics", icon: BarChart3 },
  { to: "/audit", label: "Audit Log", icon: ScrollText, minRole: "admin" },
];

const PAGE_META: Record<string, { title: string; subtitle: string }> = {
  "/dashboard": { title: "Dashboard", subtitle: "Real-time safety overview" },
  "/live": { title: "Live Detection", subtitle: "Annotated camera feeds and live events" },
  "/cameras": { title: "Cameras", subtitle: "Manage sources and AI workers" },
  "/zones": { title: "Safety Zones", subtitle: "Define severity lines per camera" },
  "/detections": { title: "Detections", subtitle: "Historical violation records" },
  "/alerts": { title: "Alerts", subtitle: "Acknowledge and triage incidents" },
  "/statistics": { title: "Detection Statistics", subtitle: "Aggregated analytics and trends" },
  "/audit": { title: "Audit Log", subtitle: "Privileged action history" },
};

export function Layout() {
  const { user, logout, hasRole } = useAuth();
  const { theme, toggle } = useTheme();
  const { connected } = useAlertsSocket();
  const location = useLocation();
  const [open, setOpen] = useState(false);

  const meta = PAGE_META[location.pathname] ?? { title: "Site Safety", subtitle: "" };
  const initials = user?.name?.slice(0, 2).toUpperCase() ?? "AD";

  return (
    <div className="app-shell">
      <aside className={`sidebar ${open ? "open" : ""}`}>
        <div className="sidebar__brand">
          <span className="sidebar__brand-icon">
            <HardHat size={22} />
          </span>
          <span>Site Safety</span>
        </div>
        <nav className="sidebar__nav">
          {NAV.filter((item) => !item.minRole || hasRole(item.minRole)).map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}
              onClick={() => setOpen(false)}
            >
              <item.icon size={18} />
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar__footer">
          <button className="btn btn-ghost" style={{ width: "100%", color: "#cbd5e1" }} onClick={logout}>
            <LogOut size={16} /> Sign out
          </button>
        </div>
      </aside>

      <div className="main">
        <header className="topbar">
          <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
            <button className="icon-btn menu-toggle" onClick={() => setOpen((o) => !o)}>
              <Menu size={18} />
            </button>
            <div className="topbar__title">
              <h1>{meta.title}</h1>
              <p>{meta.subtitle}</p>
            </div>
          </div>
          <div className="topbar__actions">
            <span className="badge badge-neutral" title="Realtime connection">
              <span className={`dot ${connected ? "dot-success" : "dot-muted"}`} />
              {connected ? "Live" : "Offline"}
            </span>
            <button className="icon-btn" onClick={toggle} aria-label="Toggle theme">
              {theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}
            </button>
            <div className="user-chip">
              <div className="avatar">{initials}</div>
              <div style={{ lineHeight: 1.2 }}>
                <div style={{ fontWeight: 600, fontSize: "0.85rem" }}>{user?.name}</div>
                <div className="helper-text" style={{ fontSize: "0.72rem" }}>
                  {user?.role.replace("_", " ")}
                </div>
              </div>
            </div>
          </div>
        </header>
        <main className="page">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
