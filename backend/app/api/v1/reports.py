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
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not yet generated for this job")
    return FileResponse(report.file_path, media_type="application/pdf", filename=f"retailvision_report_{job_id}.pdf")
