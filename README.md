# Construction Site Safety Platform

Production-grade, real-time computer-vision platform for construction-site safety
monitoring. Detects **helmet violations** and **safety-line crossings** from
camera streams, persists detections, and pushes live alerts to a polished admin
console.

This repository was refactored from a multi-microservice proof-of-concept into a
single, cohesive **MVC + Service + DAL** FastAPI backend that launches the AI
pipeline as **backend-managed multiprocessing camera workers** (one OS process
per active camera), plus a **React 19.2** admin UI.

---

## Architecture

```
┌───────────────┐   REST + WS    ┌──────────────────────────────────────┐   asyncpg   ┌──────────────┐
│  React 19.2   │ ─────────────▶ │            FastAPI Backend            │ ──────────▶ │ PostgreSQL   │
│  Admin UI     │ ◀───────────── │  Routes → Services → Repositories(DAL) │            │   18.4       │
└───────────────┘   alerts       │                 │  ▲                   │            └──────────────┘
                                 │      spawn      │  │ multiprocessing.Queue
                                 │                 ▼  │ (detections)
                                 │        WorkerSupervisor / EventDrainer  │
                                 └──────────┬──────────────────────────────┘
                                            │ one Process per active camera
                                   ┌────────▼─────────┐   writes   ┌─────────────────┐
                                   │  Camera Worker    │ ─────────▶ │ /data/live/*.jpg │ (live view)
                                   │  (ai_repo pipeline│            └─────────────────┘
                                   │  YOLOv8+ByteTrack)│
                                   └───────────────────┘
```

- **Activate a camera** → backend spawns a worker process running the `ai_repo`
  pipeline. The worker detects, tracks, evaluates helmet/line rules, publishes an
  annotated JPEG for the live view, and streams `DetectionMessage`s over a
  `multiprocessing.Queue`.
- An async **event drainer** persists those messages (through the service/DAL
  layers) and broadcasts alerts over WebSocket.
- **Deactivate** → the worker process is stopped gracefully.

### Repository layout

```
construction-site-safety-poc/
  backend/
    app/
      api/v1/routes/   controllers: auth, zones, cameras, detections, statistics, live, websocket, health, audit
      api/deps.py      DI: db session, current user, require_roles guards, pagination
      services/        business logic (auth, zone, camera, detection, statistics, audit)
      repositories/    data access layer (one class per aggregate)
      models/          SQLAlchemy ORM models
      schemas/         Pydantic DTOs (Create/Update/Read) + pagination
      core/            config, database, security, logging (hourly rotation), rate_limit, request_context
      enums/           centralized enums (Role, CameraStatus, SourceType, ViolationType, ZoneSeverity, AlertLevel)
      utils/           datetime, images, pagination helpers
      workers/         multiprocessing supervisor, registry, camera_worker, event_drainer, messages
      realtime/        WebSocket alert manager
      responses/       standard response envelope
      exceptions/      AppException hierarchy + global handlers
      main.py          app factory + lifespan
    alembic/           migration env + 0001_init
    tests/             pytest suite
    Dockerfile  pyproject.toml  requirements.txt  alembic.ini
  ai-repo/
    ai_repo/ detection/ tracking/ zones/ pipelines/ config.py
    requirements.txt  pyproject.toml
  frontend/            React 19.2 + Vite + TS (pages, components, hooks, context, services, types)
  docker-compose.yml   postgres:18.4 + backend (+auto-migrate) + frontend
  .env.example  README.md
```

---

## Tech stack

| Layer        | Technology                                            |
|--------------|-------------------------------------------------------|
| Frontend     | React 19.2, TypeScript, Vite 6, React Router 7, Recharts, lucide-react |
| Backend      | Python 3.13, FastAPI, SQLAlchemy (async), Alembic     |
| Database     | PostgreSQL 18.4                                        |
| AI pipeline  | YOLOv8 (ultralytics), ByteTrack (supervision), OpenCV |
| Auth         | JWT (HS256) + bcrypt + RBAC (`super_admin`/`admin`/`viewer`) |
| Infra        | Docker, docker-compose                                |

---

## Quick start (Docker)

```bash
cp .env.example .env          # adjust secrets as needed
docker-compose up --build
```

- Backend runs DB migrations on startup, then serves on **http://localhost:8000**
  (interactive docs at `/docs`).
- Frontend on **http://localhost:3000**.
- Default login (seeded on first startup): **admin@safety.com** / **Admin@123456**.

> The first backend build downloads the CV stack (torch/ultralytics) and can take
> several minutes.

### YOLO weights

- The person model (`yolov8n.pt`) is downloaded automatically by ultralytics.
- For helmet detection, drop a helmet model at `models/helmet_yolov8.pt` (mounted
  read-only into the backend). Without it, workers treat all persons as helmet
  violations (original PoC behaviour is preserved).
- File sources: place videos under `input_videos/` (mounted at
  `/data/input_videos`) and set a camera's stream URL to
  `/data/input_videos/your.mp4`.

---

## Local development

### Backend

```bash
cd backend
py -m venv .venv && .venv\Scripts\activate      # Windows
# source .venv/bin/activate                      # macOS/Linux
pip install -r requirements.txt
# point DATABASE_URL at a local Postgres, then:
alembic upgrade head
uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev                # http://localhost:3000 (proxies /api and /ws to :8000)
```

---

## Running tests

The suite uses an isolated SQLite database and a faked worker supervisor (no real
YOLO/processes required), so only the backend requirements are needed.

```bash
cd backend
pip install -r requirements.txt
pytest
```

Coverage includes: login + JWT, RBAC denials (403 envelope), Zone/Camera CRUD,
camera activate/deactivate, detection ingestion + retrieval + alert
acknowledgement, statistics aggregation, the response envelope + pagination +
validation errors, and unit tests for the preserved detection logic
(helmet association, bidirectional line crossing, cooldown).

---

## API surface (all under `/api/v1`, JSON envelope)

| Method | Path                              | Min role   | Notes                              |
|--------|-----------------------------------|------------|------------------------------------|
| POST   | `/auth/login`                     | public     | Rate limited (10/min)              |
| GET    | `/auth/me`                        | viewer     |                                    |
| GET/POST | `/auth/users`                   | super_admin| List / create users                |
| GET/POST/PATCH/DELETE | `/zones[/{id}]`    | viewer/admin | CRUD (mutations require admin)   |
| GET/POST/PATCH/DELETE | `/cameras[/{id}]`  | viewer/admin | CRUD                             |
| POST   | `/cameras/{id}/activate`          | admin      | Spawns worker process              |
| POST   | `/cameras/{id}/deactivate`        | admin      | Stops worker process               |
| GET    | `/detections`                     | viewer     | Paginated + filters                |
| GET    | `/alerts`                         | viewer     | Paginated                          |
| PATCH  | `/alerts/{id}`                    | admin      | Acknowledge / reopen               |
| GET    | `/statistics`                     | viewer     | Aggregated analytics               |
| GET    | `/live/{id}.jpg` · `/live/{id}/mjpeg` | viewer | Bearer header or `?token=`         |
| WS     | `/ws/alerts`                      | token      | Real-time alerts                   |
| GET    | `/audit`                          | admin      | Audit log                          |
| GET    | `/health`                         | public     |                                    |

### Standard response envelope

```json
{
  "success": true,
  "message": "OK",
  "data": {},
  "error": null,
  "meta": { "timestamp": "...", "request_id": "...", "pagination": null }
}
```

Errors use the same shape with `success: false` and a structured
`error: { code, details }`. No raw 500 stack traces leak.

---

## Configuration (`.env`)

All configuration lives in a single `.env` (loaded via `pydantic-settings`). See
[`.env.example`](.env.example) for the full annotated reference. Key groups:

- **Database**: `DATABASE_URL`, pool sizing.
- **JWT**: `JWT_SECRET_KEY`, `JWT_ALGORITHM`, `JWT_EXPIRE_HOURS`.
- **Seed admin**: `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `ADMIN_NAME`.
- **Rate limiting**: `RATE_LIMIT_DEFAULT`, `RATE_LIMIT_LOGIN`, `RATE_LIMIT_ENABLED`.
- **Storage/logging**: `DATA_DIR`, `SCREENSHOTS_DIR`, `LOGS_DIR`, `LIVE_FRAMES_DIR`, `LOG_LEVEL`.
- **AI/workers**: `YOLO_MODEL_PATH`, `HELMET_MODEL_PATH`, `CONFIDENCE_THRESHOLD`, `INFERENCE_DEVICE`, `FRAME_SKIP`, `MAX_ACTIVE_CAMERAS`, `ALERT_COOLDOWN_SECONDS`.
- **Default lines**: `GREEN_LINE_Y`, `YELLOW_LINE_Y`, `RED_LINE_Y`.

### Logging

Structured JSON logs rotate **hourly**. Rotated files are named
`dd-mm-yyyy_hh-mm-ss.log` (filename-safe separators; the colon requested in the
spec is illegal on Windows/NTFS, so `-` is substituted while preserving the
layout). Every log line carries the request-scoped `request_id`.

---

## Migrations

Schema is managed by Alembic (`backend/alembic/`); `database/init.sql` was
removed.

```bash
cd backend
alembic upgrade head                       # apply
alembic revision --autogenerate -m "msg"   # create new migration
```

The Docker backend container runs `alembic upgrade head` automatically before
starting the API.

---

## Notable changes vs. the original PoC

- `inference-service/` + `video-service/` **consolidated** into `ai-repo/`, driven
  by backend multiprocessing workers instead of always-on microservices.
- **Per-camera ByteTrack** (one tracker per worker process) fixes cross-camera ID
  collisions from the old single global tracker.
- **Zones** are now a first-class CRUD entity (severity lines bound to cameras);
  workers build their line config from a camera's active zones.
- **Unified `detections` table** (replaces `helmet_events` + `line_crossing_events`)
  powers the new **Detection Statistics** feature; `alerts` reference detections.
- **RBAC** (`super_admin`/`admin`/`viewer`) with dependency-injected route guards.
- Standard **response envelope**, **AppException** hierarchy + global handlers,
  **rate limiting**, **hourly-rotated logging**, and a full **pytest** suite.
- Server-side audio alarms were dropped (Windows-only, meaningless in Linux
  containers); the browser plays alert sounds instead.
- Postgres 16 → 18.4, React 18 → 19.2, Python → 3.13.
