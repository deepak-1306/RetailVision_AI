from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import auth, behaviours, frame_preview, insights, jobs, live, predictions, recommendations, reports, videos

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(videos.router)
api_router.include_router(frame_preview.router)
api_router.include_router(jobs.router)
api_router.include_router(live.router)
api_router.include_router(behaviours.router)
api_router.include_router(predictions.router)
api_router.include_router(recommendations.router)
api_router.include_router(reports.router)
api_router.include_router(insights.router)
