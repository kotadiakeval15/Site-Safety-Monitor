export type Role = "super_admin" | "admin" | "viewer";
export type SourceType = "cctv" | "ip" | "webcam" | "mobile" | "file";
export type CameraStatus = "inactive" | "starting" | "active" | "error";
export type DetectionMode = "restricted_area" | "helmet";
export type ZoneSeverity = "level_1" | "level_2" | "danger";
export type ViolationType = "helmet_violation" | "line_crossing";
export type CrossedLine = "green" | "yellow" | "red";
export type AlertLevel = "level_1" | "level_2" | "danger";

export interface PaginationMeta {
  page: number;
  page_size: number;
  total_items: number;
  total_pages: number;
}

export interface Meta {
  timestamp: string;
  request_id: string;
  pagination?: PaginationMeta | null;
}

export interface Envelope<T> {
  success: boolean;
  message: string;
  data: T | null;
  error: { code: string; details?: unknown } | null;
  meta: Meta;
}

export interface User {
  user_id: string;
  name: string;
  email: string;
  role: Role;
  is_active: boolean;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in_hours: number;
  user: User;
}

export interface Zone {
  zone_id: string;
  camera_id: string;
  name: string;
  description: string | null;
  severity: ZoneSeverity;
  line_y: number;
  line_x1: number | null;
  line_y1: number | null;
  line_x2: number | null;
  line_y2: number | null;
  is_active: boolean;
}

export interface Camera {
  camera_id: string;
  name: string;
  source_type: SourceType;
  stream_url: string;
  status: CameraStatus;
  detection_mode: DetectionMode;
  has_video?: boolean;
  zones: Zone[];
}

export interface Detection {
  detection_id: string;
  camera_id: string;
  zone_id: string | null;
  worker_id: number;
  violation_type: ViolationType;
  severity: ZoneSeverity;
  crossed_line: CrossedLine | null;
  confidence: number;
  bbox: number[] | null;
  foot_x: number | null;
  foot_y: number | null;
  screenshot_path: string | null;
  message: string | null;
  created_at: string;
}

export interface Alert {
  alert_id: string;
  detection_id: string;
  level: AlertLevel;
  message: string | null;
  acknowledged: boolean;
  acked_by: string | null;
  acked_at: string | null;
  created_at: string;
}

export interface AuditLog {
  log_id: string;
  action: string;
  user_id: string | null;
  details: Record<string, unknown> | null;
  created_at: string;
}

export interface CountByKey {
  key: string;
  label: string;
  count: number;
}

export interface CameraCount {
  camera_id: string;
  camera_name: string;
  count: number;
}

export interface ZoneCount {
  zone_id: string | null;
  zone_name: string;
  count: number;
}

export interface TimeBucket {
  bucket: string;
  count: number;
}

export interface StatisticsSummary {
  total_detections: number;
  total_alerts: number;
  unacknowledged_alerts: number;
  active_cameras: number;
  total_cameras: number;
  total_zones: number;
  detections_today: number;
}

export interface DetectionStatistics {
  summary: StatisticsSummary;
  by_type: CountByKey[];
  by_severity: CountByKey[];
  by_camera: CameraCount[];
  by_zone: ZoneCount[];
  over_time: TimeBucket[];
}

export interface Paged<T> {
  items: T[];
  pagination: PaginationMeta;
}
