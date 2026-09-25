"""
Application configuration.

All settings are sourced from environment variables (see .env.example at the
repo root). Defaults are chosen so the app runs out-of-the-box for a
hackathon demo with SQLite + local filesystem storage; production deployments
should override DATABASE_URL to point at PostgreSQL and set a real
SECRET_KEY / ANTHROPIC_API_KEY.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ---------- General ----------
    ENVIRONMENT: str = "development"
    PROJECT_NAME: str = "RetailVision AI"
    API_V1_PREFIX: str = "/api/v1"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"

    # ---------- Security ----------
    SECRET_KEY: str = "dev-secret-key-change-me"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 10080
    BACKEND_CORS_ORIGINS: str = '["http://localhost:5173","http://localhost:3000"]'

    # ---------- Database ----------
    # Defaults to a local SQLite file so the app runs without provisioning
    # PostgreSQL. Set DATABASE_URL to a postgresql+psycopg:// URL in
    # production / docker-compose.
    DATABASE_URL: str = "sqlite:///./retailvision.db"

    # ---------- Redis / Celery ----------
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"
    CELERY_TASK_ALWAYS_EAGER: bool = False  # True lets the pipeline run inline w/o a worker (demo mode)

    # ---------- Storage ----------
    MEDIA_ROOT: str = "./data/media"
    UPLOAD_DIR: str = "./data/media/uploads"
    PROCESSED_DIR: str = "./data/media/processed"
    REPORT_DIR: str = "./data/media/reports"
    MAX_UPLOAD_SIZE_MB: int = 500
    ALLOWED_VIDEO_EXTENSIONS: str = '[".mp4",".avi",".mov",".mkv"]'

    # ---------- AI / CV pipeline ----------
    YOLO_WEIGHTS_PATH: str = "yolo11s.pt"  # small model: better recall at low extra cost on CPU
    YOLO_CONFIDENCE_THRESHOLD: float = 0.15
    YOLO_IOU_THRESHOLD: float = 0.45
    BYTETRACK_TRACK_THRESH: float = 0.25
    BYTETRACK_TRACK_BUFFER: int = 90
    BYTETRACK_MATCH_THRESH: float = 0.20
    VIDEO_SWIN_CLIP_LEN: int = 32
    VIDEO_SWIN_FRAME_STRIDE: int = 2
    VIDEO_SWIN_WEIGHTS_PATH: str = "./ai/weights/video_swin_behaviour.pth"
    FRAME_SAMPLE_FPS: int = 3  # Optimal balance: fast cloud inference with high behavioural precision
    DEVICE: str = "cpu"  # cuda | cpu

    # ---------- Live streaming (webcam / RTSP -> WebSocket) ----------
    # Frames pushed to /api/v1/live/ws are downscaled to this width before
    # inference to keep CPU-only deployments real-time capable.
    LIVE_STREAM_MAX_WIDTH: int = 960
    LIVE_STREAM_TARGET_FPS: int = 8
    LIVE_STREAM_JPEG_QUALITY: int = 70

    # ---------- Purchase intent model ----------
    XGBOOST_MODEL_PATH: str = "./ai/weights/purchase_intent_xgb.json"

    # ---------- LLM ----------
    LLM_PROVIDER: str = "anthropic"
    ANTHROPIC_API_KEY: str = ""
    LLM_MODEL: str = "claude-sonnet-4-6"
    LLM_MAX_TOKENS: int = 1500

    @property
    def cors_origins(self) -> List[str]:
        raw = self.BACKEND_CORS_ORIGINS.strip()
        if raw == "*" or raw == '["*"]':
            return ["*"]
        try:
            if raw.startswith("["):
                return json.loads(raw)
            return [s.strip() for s in raw.split(",") if s.strip()]
        except Exception:
            return ["*"]

    @property
    def allowed_video_extensions(self) -> List[str]:
        try:
            return json.loads(self.ALLOWED_VIDEO_EXTENSIONS)
        except json.JSONDecodeError:
            return [".mp4"]

    def ensure_media_dirs(self) -> None:
        for d in (self.MEDIA_ROOT, self.UPLOAD_DIR, self.PROCESSED_DIR, self.REPORT_DIR):
            Path(d).mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_media_dirs()
