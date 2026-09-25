from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.job import ProcessingJob
from app.models.user import User
from app.models.video import Video
from app.schemas.job import JobOut

router = APIRouter(prefix="/jobs", tags=["Processing Jobs"])


def _get_owned_job(db: Session, job_id: str, user: User) -> ProcessingJob:
    job = db.get(ProcessingJob, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    video = db.get(Video, job.video_id)
    if not video or video.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job


@router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> ProcessingJob:
    return _get_owned_job(db, job_id, current_user)


@router.get("", response_model=list[JobOut])
def list_jobs(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[ProcessingJob]:
    video_ids = [v.id for v in db.query(Video).filter(Video.owner_id == current_user.id).all()]
    if not video_ids:
        return []
    return (
        db.query(ProcessingJob)
        .filter(ProcessingJob.video_id.in_(video_ids))
        .order_by(ProcessingJob.created_at.desc())
        .all()
    )


# ── Annotated video streaming with Range request support ─────────────────────

def _iter_file(path: str, start: int, end: int, chunk: int = 1024 * 256):
    """Generator that yields chunks of the file between byte positions [start, end]."""
    with open(path, "rb") as f:
        f.seek(start)
        remaining = end - start + 1
        while remaining > 0:
            data = f.read(min(chunk, remaining))
            if not data:
                break
            remaining -= len(data)
            yield data


from app.core.config import settings
from app.core.storage import resolve_media_path

@router.get("/{job_id}/annotated-video")
def get_annotated_video(
    job_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    """
    Stream the annotated MP4 with proper HTTP Range support.

    Browsers require Range requests to seek inside a video element.
    Without this, the <video> tag shows a black screen or freezes.

    Accepts ?token=<jwt> for direct browser <video src="..."> usage.
    """
    job = _get_owned_job(db, job_id, current_user)

    if not job.annotated_video_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Annotated video not yet available. Check job status.",
        )

    path = resolve_media_path(job.annotated_video_path, settings.PROCESSED_DIR)
    if not path or not path.exists() or path.stat().st_size == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Annotated video file not found on server storage.",
        )

    file_size = path.stat().st_size
    range_header = request.headers.get("Range")

    if range_header:
        # Parse "bytes=start-end"
        try:
            range_val = range_header.replace("bytes=", "")
            parts = range_val.split("-")
            start = int(parts[0]) if parts[0] else 0
            end = int(parts[1]) if parts[1] else file_size - 1
        except (ValueError, IndexError):
            start, end = 0, file_size - 1

        end = min(end, file_size - 1)
        content_length = end - start + 1

        headers = {
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(content_length),
            "Content-Type": "video/mp4",
            "Content-Disposition": f'inline; filename="retailvision_{job_id}_annotated.mp4"',
        }
        return StreamingResponse(
            _iter_file(str(path), start, end),
            status_code=206,
            headers=headers,
            media_type="video/mp4",
        )

    # Full file (no Range header)
    headers = {
        "Accept-Ranges": "bytes",
        "Content-Length": str(file_size),
        "Content-Type": "video/mp4",
        "Content-Disposition": f'inline; filename="retailvision_{job_id}_annotated.mp4"',
    }
    return StreamingResponse(
        _iter_file(str(path), 0, file_size - 1),
        status_code=200,
        headers=headers,
        media_type="video/mp4",
    )


@router.get("/{job_id}/download-annotated-video")
def download_annotated_video(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FileResponse:
    """Download the annotated video as a file attachment."""
    job = _get_owned_job(db, job_id, current_user)
    if not job.annotated_video_path:
        raise HTTPException(status_code=404, detail="Annotated video not available")
    path = resolve_media_path(job.annotated_video_path, settings.PROCESSED_DIR)
    if not path or not path.exists():
        raise HTTPException(status_code=404, detail="File not found on server")
    return FileResponse(
        str(path),
        media_type="video/mp4",
        filename=f"retailvision_{job_id}_annotated.mp4",
    )


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_job(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a job, its video, and all associated analytics data completely."""
    from app.services.job_service import delete_job_and_associated_data
    
    # ensure it exists and belongs to user
    _ = _get_owned_job(db, job_id, current_user)
    
    success = delete_job_and_associated_data(db, job_id, current_user.id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete job and associated data")
    return None
