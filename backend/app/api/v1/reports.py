from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.v1.jobs import _get_owned_job
from app.db.session import get_db
from app.models.report import Report
from app.models.user import User
from app.schemas.report import ReportOut

from app.core.config import settings
from app.core.storage import resolve_media_path

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("/{job_id}", response_model=ReportOut)
def get_report(job_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> Report:
    _get_owned_job(db, job_id, current_user)
    report = db.query(Report).filter(Report.job_id == job_id).order_by(Report.generated_at.desc()).first()
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not yet generated for this job")
    return report


@router.get("/{job_id}/download")
def download_report(job_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> FileResponse:
    _get_owned_job(db, job_id, current_user)
    report = db.query(Report).filter(Report.job_id == job_id).order_by(Report.generated_at.desc()).first()
    if not report or not report.file_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not yet generated for this job")
    path = resolve_media_path(report.file_path, settings.REPORT_DIR)
    if not path or not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report file not found on server")
    return FileResponse(str(path), media_type="application/pdf", filename=f"retailvision_report_{job_id}.pdf")
