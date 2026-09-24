# syntax=docker/dockerfile:1

# ------------------------------------------------------------------------------
# Stage 1: Build Frontend (Vite + React)
# ------------------------------------------------------------------------------
FROM node:22-alpine AS frontend-builder
WORKDIR /app/frontend

COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install

COPY frontend ./
# Build production bundle to /app/frontend/dist
RUN npm run build

# ------------------------------------------------------------------------------
# Stage 2: Production Python Backend + Integrated Static Frontend
# ------------------------------------------------------------------------------
FROM python:3.11-slim AS production

# System dependencies for OpenCV, FFmpeg video processing, and compilation
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python requirements
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r /app/backend/requirements.txt

# Copy backend code, AI modules, and weights
COPY backend /app/backend
COPY ai /app/ai
COPY yolo11s.pt /app/yolo11s.pt
COPY yolo11s.pt /app/backend/yolo11s.pt

# Copy built frontend assets into the container
COPY --from=frontend-builder /app/frontend/dist /app/frontend/dist

# Create necessary media storage directories
RUN mkdir -p /app/backend/data/media/uploads \
             /app/backend/data/media/processed \
             /app/backend/data/media/reports \
             /app/data/media/uploads \
             /app/data/media/processed \
             /app/data/media/reports

ENV PYTHONPATH=/app/backend:/app \
    PYTHONUNBUFFERED=1 \
    ENVIRONMENT=production \
    CELERY_TASK_ALWAYS_EAGER=true \
    BACKEND_CORS_ORIGINS="*" \
    FRAME_SAMPLE_FPS=5 \
    YOLO_WEIGHTS_PATH=yolo11s.pt \
    VIDEO_SWIN_WEIGHTS_PATH=/app/backend/ai/weights/video_swin_behaviour.pth \
    PORT=8000

WORKDIR /app/backend

EXPOSE 8000

# Start Uvicorn dynamically binding to the port assigned by Render ($PORT) or 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
