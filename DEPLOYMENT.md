# 🚀 RetailVision AI — Cloud & Production Deployment Guide

This guide provides comprehensive, step-by-step instructions to deploy **RetailVision AI** to **Render**, **Railway**, **AWS/GCP**, or any **Docker VPS**.

---

## 🌟 Option 1: Render Deployment (Recommended)

Render offers the fastest and most cost-effective way to host RetailVision AI with full Docker, FFmpeg, and OpenCV support.

### ⚡ Method A: 1-Click Render Blueprint (`render.yaml`)

1. **Push your code to GitHub / GitLab**:
   ```bash
   git add .
   git commit -m "Configure production deployment for Render"
   git push origin main
   ```

2. **Open the Render Dashboard**:
   - Go to [dashboard.render.com](https://dashboard.render.com).
   - Click **New +** in the top right corner and select **Blueprint**.

3. **Connect your Repository**:
   - Select your `RetailVision` repository.
   - Render will automatically detect the [`render.yaml`](./render.yaml) file in the root directory.

4. **Review & Deploy**:
   - Set the instance plan (**Starter** or above is recommended for video processing & PyTorch/OpenCV).
   - (Optional) Set `ANTHROPIC_API_KEY` if you want Claude-powered retail insights.
   - Click **Apply** / **Deploy**.

---

### 🛠️ Method B: Manual Web Service on Render

If you prefer to configure the Web Service manually:

1. In Render Dashboard, click **New +** → **Web Service**.
2. Connect your Git repository.
3. Choose the following settings:
   - **Name**: `retailvision-ai`
   - **Runtime**: `Docker`
   - **Dockerfile Path**: `Dockerfile`
   - **Docker Context**: `.`
   - **Plan**: `Starter` (0.5+ CPU, 1GB+ RAM recommended for video decoding)
4. Add the following **Environment Variables**:
   | Key | Value | Description |
   |---|---|---|
   | `ENVIRONMENT` | `production` | Production mode |
   | `PROJECT_NAME` | `RetailVision AI` | Project title |
   | `DEBUG` | `false` | Disable debug banner |
   | `SECRET_KEY` | *(Click Generate)* | Strong JWT signing secret |
   | `BACKEND_CORS_ORIGINS` | `*` | Allow web traffic |
   | `CELERY_TASK_ALWAYS_EAGER` | `true` | Process videos inline (no Redis required) |
   | `FRAME_SAMPLE_FPS` | `5` | AI pipeline sample rate |
   | `YOLO_WEIGHTS_PATH` | `yolo11s.pt` | YOLOv11 small weights |
   | `ANTHROPIC_API_KEY` | `sk-ant-...` | *(Optional)* Claude retail suggestions |
5. Add a **Persistent Disk** (Optional but recommended for storing uploaded videos):
   - **Mount Path**: `/app/backend/data/media`
   - **Size**: `10 GB`
6. Click **Create Web Service**.

Your live URL will be: `https://retailvision-ai.onrender.com` (serving both the React UI and FastAPI backend with 0 CORS issues).

---

## 🚂 Option 2: Railway Deployment

Railway automatically supports Dockerfiles with zero configuration:

1. Go to [railway.app](https://railway.app) and create a **New Project**.
2. Choose **Deploy from GitHub repo** and pick this repository.
3. Railway will build the root [`Dockerfile`](./Dockerfile).
4. In Settings → **Networking**, click **Generate Domain** (e.g. `retailvision.up.railway.app`).
5. In Variables, add `SECRET_KEY` and `CELERY_TASK_ALWAYS_EAGER=true`.

---

## 🐳 Option 3: Self-Hosted Docker VPS (Ubuntu / Debian / Windows Server)

For private servers or AWS EC2 / Lightsail:

### 1. Clone & Setup Environment
```bash
git clone <your-repo-url>
cd cv1
cp .env.example .env
```

### 2. Build & Launch with Docker Compose
```bash
# Production single-container build:
docker build -t retailvision-ai .
docker run -d -p 8000:8000 --name retailvision -v retailvision_data:/app/backend/data/media retailvision-ai

# Or multi-container with Redis + Postgres + Celery Worker:
docker compose up -d --build
```

Access the application at `http://<your-server-ip>:8000` (or `http://localhost:5173` for multi-container).

---

## 🌐 Quick Public Tunnel (ngrok / Cloudflare Tunnel)

If you want to instantly share your current local running application without cloud hosting:

```powershell
# Expose the unified backend (serving UI + API):
ngrok http 8000
```
or with Cloudflare Tunnel:
```powershell
cloudflared tunnel --url http://localhost:8000
```

---

## 🔍 Verification & Health Check

After deployment, check:
- **Web UI**: Visit your deployed URL (e.g. `https://retailvision-ai.onrender.com`).
- **Health Check**: `https://retailvision-ai.onrender.com/health` (Returns `{"status": "ok"}`).
- **Interactive Swagger Docs**: `https://retailvision-ai.onrender.com/docs`.
