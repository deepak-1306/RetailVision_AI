from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.job import JobStatus, ProcessingJob
from app.models.video import Video
from ai.preprocessing.video_preprocessor import VideoPreprocessor


def save_upload(db: Session, owner_id: str, file: UploadFile) -> tuple[Video, ProcessingJob]:
    ext = Path(file.filename or "video.mp4").suffix.lower()
    if ext not in settings.allowed_video_extensions:
        raise ValueError(f"Unsupported file type '{ext}'. Allowed: {settings.allowed_video_extensions}")

    stored_name = f"{uuid.uuid4()}{ext}"
    dest_path = Path(settings.UPLOAD_DIR) / stored_name
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    with dest_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Extract basic metadata up front so the UI has something to show immediately
    duration = fps = width = height = None
    try:
        meta = VideoPreprocessor(str(dest_path)).get_metadata()
        duration, fps, width, height = meta.duration_seconds, meta.fps, meta.width, meta.height
    except Exception:
        pass  # metadata is best-effort; the pipeline will surface hard failures

    video = Video(
        owner_id=owner_id,
        filename=stored_name,
        storage_path=dest_path.as_posix(),
        original_name=file.filename or stored_name,
        duration_seconds=duration,
        fps=fps,
        width=width,
        height=height,
    )
    db.add(video)
    db.commit()
    db.refresh(video)

    job = ProcessingJob(video_id=video.id, status=JobStatus.PENDING, progress=0)
    db.add(job)
    db.commit()
    db.refresh(job)

    return video, job
