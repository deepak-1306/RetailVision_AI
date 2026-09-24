# syntax=docker/dockerfile:1

FROM python:3.12-slim AS base

# System dependencies required by OpenCV, PyTorch, and video decoding
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first for better layer caching
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r /app/backend/requirements.txt

# Copy application source (also bind-mounted in dev via docker-compose)
COPY backend /app/backend
COPY ai /app/ai

ENV PYTHONPATH=/app/backend:/app \
    PYTHONUNBUFFERED=1

WORKDIR /app/backend

RUN mkdir -p /data/media/uploads /data/media/processed /data/media/reports

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
