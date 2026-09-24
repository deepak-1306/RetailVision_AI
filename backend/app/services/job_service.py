from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.job import JobStatus, ProcessingJob


def update_job_status(db: Session, job_id: str, status: str, progress: int, error_message: str | None = None) -> None:
    job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
    if not job:
        return

    job.status = JobStatus(status) if status in JobStatus._value2member_map_ else job.status
    job.progress = progress
    if error_message:
        job.error_message = error_message
    if status == "preprocessing" and job.started_at is None:
        job.started_at = datetime.now(timezone.utc)
    if status in ("completed", "failed"):
        job.completed_at = datetime.now(timezone.utc)

    db.add(job)
    db.commit()


def delete_job_and_associated_data(db: Session, job_id: str, owner_id: str) -> bool:
    import os
    job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
    if not job:
        return False

    video = job.video
    if video.owner_id != owner_id:
        return False

    # Delete physical files
    if video.storage_path and os.path.exists(video.storage_path):
        try:
            os.remove(video.storage_path)
        except OSError:
            pass

    if job.annotated_video_path and os.path.exists(job.annotated_video_path):
        try:
            os.remove(job.annotated_video_path)
        except OSError:
            pass

    # Delete video from DB (this cascades to job, behaviours, predictions, recommendations, reports)
    db.delete(video)
    db.commit()
    return True

