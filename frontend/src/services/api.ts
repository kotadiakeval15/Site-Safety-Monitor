import type {
  Alert,
  AuditLog,
  Camera,
  Detection,
  DetectionStatistics,
  Envelope,
  Paged,
  TokenResponse,
  User,
  Zone,
} from "../types";
import { encryptPassword } from "./crypto";

const API_URL = import.meta.env.VITE_API_URL || "";
const TOKEN_KEY = "css_token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

export class ApiError extends Error {
  code: string;
  status: number;
  details?: unknown;
  constructor(message: string, code: string, status: number, details?: unknown) {
    super(message);
    this.code = code;
    this.status = status;
    this.details = details;
  }
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  query?: Record<string, string | number | boolean | undefined | null>;
}

function buildQuery(query?: RequestOptions["query"]): string {
  if (!query) return "";
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== null && value !== "") {
      params.append(key, String(value));
    }
  }
  const qs = params.toString();
  return qs ? `?${qs}` : "";
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<Envelope<T>> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  const response = await fetch(`${API_URL}${path}${buildQuery(options.query)}`, {
    method: options.method ?? "GET",
    headers,
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
  });

  if (response.status === 401 && !path.includes("/auth/login")) {
    clearToken();
    if (window.location.pathname !== "/login") window.location.href = "/login";
  }

  let payload: Envelope<T>;
  try {
    payload = (await response.json()) as Envelope<T>;
  } catch {
    throw new ApiError("Unexpected server response", "network_error", response.status);
  }

  if (!response.ok || !payload.success) {
    throw new ApiError(
      payload?.message ?? "Request failed",
      payload?.error?.code ?? "error",
      response.status,
      payload?.error?.details,
    );
  }
  return payload;
}

function paged<T>(envelope: Envelope<T[]>): Paged<T> {
  return {
    items: envelope.data ?? [],
    pagination:
      envelope.meta.pagination ?? {
        page: 1,
        page_size: (envelope.data ?? []).length,
        total_items: (envelope.data ?? []).length,
        total_pages: 1,
      },
  };
}

export const api = {
  // -- auth --
  async login(email: string, password: string): Promise<TokenResponse> {
    const keyRes = await request<{ public_key: string }>("/api/v1/auth/public-key");
    const publicKey = (keyRes.data as { public_key: string }).public_key;
    const encrypted = await encryptPassword(password, publicKey);
    const res = await request<TokenResponse>("/api/v1/auth/login", {
      method: "POST",
      body: { email, password: encrypted, encrypted: true },
    });
    return res.data as TokenResponse;
  },
  async me(): Promise<User> {
    return (await request<User>("/api/v1/auth/me")).data as User;
  },
  async listUsers(): Promise<User[]> {
    return (await request<User[]>("/api/v1/auth/users")).data ?? [];
  },

  // -- zones --
  async listZones(): Promise<Zone[]> {
    return (await request<Zone[]>("/api/v1/zones")).data ?? [];
  },
  async createZone(body: Partial<Zone>): Promise<Zone> {
    return (await request<Zone>("/api/v1/zones", { method: "POST", body })).data as Zone;
  },
  async updateZone(id: string, body: Partial<Zone>): Promise<Zone> {
    return (await request<Zone>(`/api/v1/zones/${id}`, { method: "PUT", body })).data as Zone;
  },
  async deleteZone(id: string): Promise<void> {
    await request(`/api/v1/zones/${id}`, { method: "DELETE" });
  },

  // -- cameras --
  async listCameras(): Promise<Camera[]> {
    return (await request<Camera[]>("/api/v1/cameras")).data ?? [];
  },
  async createCamera(body: Partial<Camera>): Promise<Camera> {
    return (await request<Camera>("/api/v1/cameras", { method: "POST", body })).data as Camera;
  },
  async updateCamera(id: string, body: Partial<Camera>): Promise<Camera> {
    return (await request<Camera>(`/api/v1/cameras/${id}`, { method: "PUT", body }))
      .data as Camera;
  },
  async deleteCamera(id: string): Promise<void> {
    await request(`/api/v1/cameras/${id}`, { method: "DELETE" });
  },
  async uploadCameraVideo(id: string, file: File): Promise<Camera> {
    const token = getToken();
    const formData = new FormData();
    formData.append("file", file);
    const response = await fetch(`${API_URL}/api/v1/cameras/${id}/video`, {
      method: "POST",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: formData,
    });
    let payload: Envelope<Camera>;
    try {
      payload = (await response.json()) as Envelope<Camera>;
    } catch {
      throw new ApiError("Unexpected server response", "network_error", response.status);
    }
    if (!response.ok || !payload.success) {
      throw new ApiError(
        payload?.message ?? "Upload failed",
        payload?.error?.code ?? "error",
        response.status,
        payload?.error?.details,
      );
    }
    return payload.data as Camera;
  },
  cameraVideoUrl(id: string): string {
    const token = getToken() ?? "";
    return `${API_URL}/api/v1/cameras/${id}/video?token=${encodeURIComponent(token)}`;
  },
  async activateCamera(id: string): Promise<Camera> {
    return (await request<Camera>(`/api/v1/cameras/${id}/activate`, { method: "POST" }))
      .data as Camera;
  },
  async deactivateCamera(id: string): Promise<Camera> {
    return (await request<Camera>(`/api/v1/cameras/${id}/deactivate`, { method: "POST" }))
      .data as Camera;
  },

  // -- detections & alerts --
  async listDetections(query: RequestOptions["query"]): Promise<Paged<Detection>> {
    return paged(await request<Detection[]>("/api/v1/detections", { query }));
  },
  async listAlerts(query: RequestOptions["query"]): Promise<Paged<Alert>> {
    return paged(await request<Alert[]>("/api/v1/alerts", { query }));
  },
  async acknowledgeAlert(id: string, acknowledged: boolean): Promise<Alert> {
    return (
      await request<Alert>(`/api/v1/alerts/${id}`, {
        method: "PUT",
        body: { acknowledged },
      })
    ).data as Alert;
  },

  // -- statistics --
  async statistics(windowHours: number): Promise<DetectionStatistics> {
    return (
      await request<DetectionStatistics>("/api/v1/statistics", {
        query: { window_hours: windowHours },
      })
    ).data as DetectionStatistics;
  },

  // -- audit --
  async listAudit(): Promise<AuditLog[]> {
    return (await request<AuditLog[]>("/api/v1/audit")).data ?? [];
  },

  // -- health --
  async health(): Promise<{ status: string; database: string; version: string }> {
    return (await request<{ status: string; database: string; version: string }>(
      "/api/v1/health",
    )).data as { status: string; database: string; version: string };
  },

  liveFrameUrl(cameraId: string): string {
    const token = getToken() ?? "";
    return `${API_URL}/api/v1/live/${cameraId}.jpg?token=${encodeURIComponent(token)}`;
  },
};

export function getWsUrl(): string {
  const token = getToken() ?? "";
  const base =
    import.meta.env.VITE_WS_URL ||
    `${window.location.protocol === "https:" ? "wss:" : "ws:"}//${window.location.host}`;
  return `${base}/api/v1/ws/alerts?token=${encodeURIComponent(token)}`;
}
