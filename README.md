# RetailVision AI

**AI-Powered Retail Customer Behaviour Analytics & Retail Decision Support System**

RetailVision AI ingests retail CCTV footage and turns it into actionable business
intelligence: it detects and tracks customers, classifies their in-store behaviour
(viewing, touching, picking, returning, etc.), predicts purchase intent, and
generates concrete merchandising recommendations — all surfaced through a live
dashboard and a downloadable PDF report.

---

## 1. Architecture

```
                 ┌─────────────────────────────────────────────────────────────┐
                 │                        FRONTEND (React 19)                  │
                 │  Landing · Auth · Dashboard · Upload · Timeline · Reports    │
                 └───────────────────────────▲─────────────────────────────────┘
                                              │ REST (Axios) / JWT
                 ┌───────────────────────────┴─────────────────────────────────┐
                 │                     BACKEND (FastAPI)                       │
                 │  Auth · Videos · Jobs · Behaviours · Predictions · Reports   │
                 └───────┬───────────────────────────────────────────┬─────────┘
                         │                                           │
                 ┌───────▼────────┐                          ┌───────▼────────┐
                 │  PostgreSQL     │                          │  Redis         │
                 │  (system data)  │                          │  (broker +     │
                 └────────────────┘                          │   cache)       │
                                                               └───────▲────────┘
                                                                       │
                 ┌─────────────────────────────────────────────────── ┴────────┐
                 │                  CELERY WORKER (async video pipeline)       │
                 │                                                             │
                 │  Preprocess → YOLOv11 Detect → ByteTrack → Video Swin       │
                 │  Behaviour Recognition → Feature Engineering →              │
                 │  XGBoost Purchase Intent → Recommendation Engine →          │
                 │  LLM Business Insight Generator → PDF Report                │
                 └─────────────────────────────────────────────────────────────┘
```

**Design principle:** the API layer never blocks on video processing. Upload
returns immediately with a `job_id`; a Celery worker runs the full CV/ML
pipeline asynchronously and streams job status back to the frontend, which
polls / subscribes to `/api/v1/jobs/{id}`.

## 2. Repository layout

```
retailvision-ai/
├── frontend/          React 19 + TypeScript + Vite + Tailwind + Shadcn UI SaaS dashboard
├── backend/            FastAPI application (REST API, auth, DB models, Celery task glue)
├── ai/                 Computer vision & ML pipeline (YOLOv11, ByteTrack, Video Swin,
│                        XGBoost purchase-intent model, recommendation engine, LLM insights)
├── database/            SQL schema reference + seed data
├── docker/              Dockerfiles for each service
├── docs/                 Architecture notes, API reference, model cards
├── tests/                PyTest (backend, ai) + React Testing Library (frontend)
├── scripts/              Dev/setup/utility scripts
├── docker-compose.yml
├── .env.example
└── README.md
```

## 3. Technology stack

| Layer | Stack |
|---|---|
| Frontend | React 19, TypeScript, Vite, Tailwind CSS, Shadcn UI, Framer Motion, Recharts, React Router, Axios |
| Backend | FastAPI, Python 3.12, SQLAlchemy 2.0, PostgreSQL, Alembic, Celery, Redis |
| Computer Vision | OpenCV, YOLOv11 (Ultralytics), ByteTrack |
| Behaviour Recognition | Video Swin Transformer |
| ML | PyTorch, XGBoost, Pandas, NumPy, Scikit-learn |
| Reporting | ReportLab |
| Deployment | Docker, Docker Compose |
| Testing | PyTest, React Testing Library |

## 4. Build plan (this repo is generated module-by-module)

This repository is being built incrementally, one production-quality module at
a time, with each module fully wired into the ones before it:

1. **Project scaffolding & infrastructure** ← *you are here*
2. Database schema & models (PostgreSQL + SQLAlchemy + Alembic)
3. Backend core (config, security, auth, FastAPI app skeleton)
4. Backend API routes (upload, jobs, behaviours, predictions, recommendations, reports)
5. Computer vision pipeline (preprocessing, YOLOv11 detection, ByteTrack tracking)
6. Behaviour recognition (Video Swin Transformer inference + timeline generation)
7. Machine learning (feature engineering + XGBoost purchase intent model)
8. Recommendation engine + LLM business insight generator
9. Celery task orchestration wiring the full pipeline end-to-end
10. PDF report generation (ReportLab)
11. Frontend foundation (Vite/React/Tailwind/Shadcn scaffold, routing, auth, API client)
12. Frontend pages (Landing, Login, Dashboard, Upload, Processing, Timeline, Analytics,
    Purchase Intent, Recommendations, Reports, Settings)
13. Tests (backend, ai, frontend) + CI
14. Final Docker Compose integration pass + docs polish

## 5. Quick start

### Option A — Docker Compose (full stack: Postgres, Redis, Celery worker)

```bash
cp .env.example .env
docker compose up --build
```

- Frontend: http://localhost:5173
- Backend API docs: http://localhost:8000/docs
- Celery Flower (task monitor): http://localhost:5555
- PostgreSQL: localhost:5432
- Redis: localhost:6379

### Option B — Local dev without Docker (fastest for hackathon demos)

The backend defaults to **SQLite** (`DATABASE_URL=sqlite:///./retailvision.db`)
and auto-creates all tables on startup — no separate database provisioning
or migration step required.

```bash
# Terminal 1 — backend API
./scripts/dev_backend.sh

# Terminal 2 — frontend
cp frontend/.env.example frontend/.env
./scripts/dev_frontend.sh

# Terminal 3 — Celery worker (optional)
# Requires a local Redis, OR set CELERY_TASK_ALWAYS_EAGER=true in backend/.env
# to run the AI pipeline synchronously on upload with no worker/Redis at all.
./scripts/dev_celery.sh
```

Open http://localhost:5173, register an account, and upload a retail CCTV clip.

### Running tests

```bash
pip install pytest --break-system-packages
pytest tests/ -v
```

## 6. What's implemented vs. what's stubbed for extension

Every stage in the pipeline diagram in §1 runs end-to-end and is fully wired
from upload → dashboard → PDF report:

- **YOLOv11 detection** — real `ultralytics` inference (auto-downloads
  `yolo11n.pt` on first run; swap in a retail-fine-tuned checkpoint via
  `YOLO_WEIGHTS_PATH`).
- **ByteTrack tracking** — a from-scratch two-stage (high/low confidence)
  IoU tracker implementing ByteTrack's core association strategy.
- **Behaviour recognition** — `ai/behaviour/behaviour_classifier.py` is
  architected around a Video Swin Transformer clip classifier
  (`VideoSwinBehaviourClassifier`), which activates automatically once a
  fine-tuned checkpoint is dropped into `ai/weights/`. Without one, it
  transparently falls back to a deterministic, explainable heuristic
  classifier operating on track motion statistics — so the full demo runs
  today without requiring a labeled training dataset.
- **Purchase intent (XGBoost)** — trains itself on first run from a
  domain-informed synthetic dataset (see `ai/ml/train_purchase_intent.py`
  docstring) so predictions work immediately; swap in real POS-linked
  training data for production.
- **Recommendation engine** — fully rule-based, no stubs.
- **LLM insight generator** — calls the Anthropic API when `ANTHROPIC_API_KEY`
  is set; otherwise falls back to a deterministic templated summary so the
  dashboard and PDF report never break in an offline/demo environment.
- **PDF reports, auth, all REST APIs, and the full React dashboard** — fully
  implemented, no placeholders.

Database migrations (Alembic) were intentionally left out of this build per
request — models auto-create their tables via SQLAlchemy on startup instead.

## 7. License

MIT — see `LICENSE`.
#   R e t a i l V i s i o n _ A I  
 