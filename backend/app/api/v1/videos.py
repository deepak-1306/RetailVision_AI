from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.db.session import get_db
from app.models.job import ProcessingJob
from app.models.user import User
from app.models.video import Video
from app.schemas.job import JobOut
from app.schemas.video import VideoOut, VideoUploadResponse
from app.services.video_service import save_upload
from app.tasks.pipeline_task import run_pipeline_for_job

router = APIRouter(prefix="/videos", tags=["Videos"])


@router.post("/upload", response_model=VideoUploadResponse, status_code=status.HTTP_201_CREATED)
def upload_video(
    file: UploadFile,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> VideoUploadResponse:
    if file.size and file.size > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"File exceeds {settings.MAX_UPLOAD_SIZE_MB}MB limit")

    try:
        video, job = save_upload(db, current_user.id, file)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    # Dispatch pipeline in background so the HTTP response returns immediately.
    # This works with or without Redis/Celery — BackgroundTasks runs in the same
    # process after the response is sent.
    background_tasks.add_task(run_pipeline_for_job, job.id)

    return VideoUploadResponse(video=VideoOut.model_validate(video), job_id=job.id)


@router.get("", response_model=list[VideoOut])
def list_videos(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[Video]:
    return db.query(Video).filter(Video.owner_id == current_user.id).order_by(Video.uploaded_at.desc()).all()


@router.get("/{video_id}", response_model=VideoOut)
def get_video(video_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> Video:
    video = db.query(Video).filter(Video.id == video_id, Video.owner_id == current_user.id).first()
    if not video:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")
    return video


@router.get("/{video_id}/jobs", response_model=list[JobOut])
def get_video_jobs(video_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[ProcessingJob]:
    video = db.query(Video).filter(Video.id == video_id, Video.owner_id == current_user.id).first()
    if not video:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")
    return db.query(ProcessingJob).filter(ProcessingJob.video_id == video_id).order_by(ProcessingJob.created_at.desc()).all()


@router.delete("/{video_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_video(video_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    video = db.query(Video).filter(Video.id == video_id, Video.owner_id == current_user.id).first()
    if not video:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")

    import os
    # Delete the original video file
    if video.storage_path and os.path.exists(video.storage_path):
        try:
            os.remove(video.storage_path)
        except OSError:
            pass

    from app.models.behaviour import BehaviourEvent
    from app.models.prediction import PurchaseIntentPrediction
    from app.models.recommendation import Recommendation
    from app.models.report import Report
    from app.models.job import ProcessingJob
    
    # Delete annotated videos, PDF reports, and all database records explicitly 
    # to handle SQLite deployments where PRAGMA foreign_keys is not ON by default.
    for job in video.jobs:
        if job.annotated_video_path and os.path.exists(job.annotated_video_path):
            try:
                os.remove(job.annotated_video_path)
            except OSError:
                pass
        for report in job.reports:
            if report.file_path and os.path.exists(report.file_path):
                try:
                    os.remove(report.file_path)
                except OSError:
                    pass
        
        db.query(BehaviourEvent).filter(BehaviourEvent.job_id == job.id).delete()
        db.query(PurchaseIntentPrediction).filter(PurchaseIntentPrediction.job_id == job.id).delete()
        db.query(Recommendation).filter(Recommendation.job_id == job.id).delete()
        db.query(Report).filter(Report.job_id == job.id).delete()
        
    db.query(ProcessingJob).filter(ProcessingJob.video_id == video.id).delete()

    # Delete from database (now all children are manually deleted)
    db.delete(video)
    db.commit()
    return None
