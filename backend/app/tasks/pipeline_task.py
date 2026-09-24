"""
Pipeline execution helpers.

Two entry points:
  1. `run_pipeline_for_job(job_id, db)` — pure function called by FastAPI
     BackgroundTasks (no Celery required).  Replaces the Celery task for the
     CELERY_TASK_ALWAYS_EAGER=True demo mode.

  2. `process_video_job` — the original Celery task, kept for deployments
     that actually run a Redis broker + Celery worker.

Both call the same `_execute(job_id, db)` implementation, which:
  1. Runs the full AI pipeline (YOLO → ByteTrack → behaviour → intent → recs)
  2. Generates an annotated MP4 (cv2.VideoWriter)
  3. Persists everything to the database
  4. Generates the LLM insight narrative + PDF report
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_backend_dir = Path(__file__).resolve().parent.parent.parent
_repo_root = _backend_dir.parent
for _p in [str(_repo_root), str(_backend_dir)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from app.core.config import settings
from app.db.base import SessionLocal
from app.models.behaviour import BehaviourEvent, BehaviourType
from app.models.job import JobStatus, ProcessingJob
from app.models.prediction import PurchaseIntentPrediction
from app.models.recommendation import Recommendation
from app.models.report import Report
from app.models.video import Video
from app.services.analytics_service import (
    get_behaviour_distribution,
    get_purchase_intent_summary,
    get_recommendations_dicts,
    get_zone_summaries,
)
from app.services.job_service import update_job_status
from app.services.report_service import generate_pdf_report
from app.tasks.celery_app import celery_app
from ai.llm.insight_generator import JobAnalyticsContext, LLMInsightGenerator
from ai.pipeline.run_pipeline import PipelineConfig, run_pipeline
from ai.pipeline.video_annotator import generate_annotated_video


def _execute(job_id: str, db) -> str:
    """
    Core pipeline execution shared by the BackgroundTask runner and the
    Celery task. Runs entirely with the provided db Session.
    """
    job = db.get(ProcessingJob, job_id)
    if job is None:
        return "job not found"
    video = db.get(Video, job.video_id)
    if video is None:
        update_job_status(db, job_id, JobStatus.FAILED.value, 0, "Video not found")
        return "video not found"

    def on_progress(status: str, progress: int) -> None:
        update_job_status(db, job_id, status, progress)

    config = PipelineConfig(
        yolo_weights_path=settings.YOLO_WEIGHTS_PATH,
        yolo_confidence_threshold=settings.YOLO_CONFIDENCE_THRESHOLD,
        yolo_iou_threshold=settings.YOLO_IOU_THRESHOLD,
        bytetrack_track_thresh=settings.BYTETRACK_TRACK_THRESH,
        bytetrack_match_thresh=settings.BYTETRACK_MATCH_THRESH,
        bytetrack_track_buffer=settings.BYTETRACK_TRACK_BUFFER,
        video_swin_weights_path=settings.VIDEO_SWIN_WEIGHTS_PATH,
        video_swin_clip_len=settings.VIDEO_SWIN_CLIP_LEN,
        video_swin_frame_stride=settings.VIDEO_SWIN_FRAME_STRIDE,
        frame_sample_fps=settings.FRAME_SAMPLE_FPS,
        device=settings.DEVICE,
        xgboost_model_path=settings.XGBOOST_MODEL_PATH,
    )

    result = run_pipeline(video.storage_path, config, progress_cb=on_progress)

    # ---- Persist behaviour events ----
    for seg in result.behaviour_segments:
        db.add(BehaviourEvent(
            job_id=job_id,
            track_id=seg.track_id,
            behaviour_type=BehaviourType(seg.behaviour_type),
            start_time_seconds=seg.start_time,
            end_time_seconds=seg.end_time,
            confidence=seg.confidence,
            shelf_zone=seg.shelf_zone,
            bbox_x=seg.bbox[0], bbox_y=seg.bbox[1],
            bbox_w=seg.bbox[2] - seg.bbox[0], bbox_h=seg.bbox[3] - seg.bbox[1],
        ))

    # ---- Persist purchase-intent predictions ----
    for track_id, features in result.customer_features.items():
        score, label = result.predictions[track_id]
        db.add(PurchaseIntentPrediction(
            job_id=job_id,
            track_id=track_id,
            dwell_time_seconds=features.dwell_time_seconds,
            touch_count=features.touch_count,
            pick_count=features.pick_count,
            return_count=features.return_count,
            viewing_duration_seconds=features.viewing_duration_seconds,
            purchase_intent_score=score,
            intent_label=label,
        ))

    # ---- Persist recommendations ----
    for rec in result.recommendations:
        db.add(Recommendation(
            job_id=job_id,
            shelf_zone=rec.shelf_zone,
            trigger_pattern=rec.trigger_pattern,
            priority=rec.priority,
            title=rec.title,
            description=rec.description,
            affected_customers=rec.affected_customers,
        ))

    db.commit()

    # ---- Generate annotated MP4 ----
    update_job_status(db, job_id, "annotating_video", 72)
    annotated_path = str(
        Path(settings.PROCESSED_DIR) / f"{job_id}_annotated.mp4"
    )
    try:
        generate_annotated_video(
            input_video_path=video.storage_path,
            output_video_path=annotated_path,
            segments=getattr(result, "raw_segments", result.behaviour_segments),
            predictions=result.predictions,
            progress_cb=lambda status, pct: update_job_status(
                db, job_id, status, 72 + int(pct * 0.18)  # maps 0-100 → 72-90
            ),
        )
        # Persist the path to the job record
        job_record = db.get(ProcessingJob, job_id)
        if job_record:
            job_record.annotated_video_path = annotated_path
            db.add(job_record)
            db.commit()
    except Exception as ann_exc:
        # Video annotation failure is non-fatal — log it but continue to
        # generate the report and insights so the rest of the dashboard works.
        update_job_status(
            db, job_id, "annotating_video", 87,
            error_message=f"[annotation warning] {ann_exc}",
        )

    # ---- LLM insight + PDF report ----
    update_job_status(db, job_id, "generating_insights", 88)
    context = JobAnalyticsContext(
        behaviour_distribution={i["behaviour_type"]: i["count"] for i in get_behaviour_distribution(db, job_id)},
        zone_summaries=get_zone_summaries(db, job_id),
        purchase_intent_summary=get_purchase_intent_summary(db, job_id),
        recommendations=get_recommendations_dicts(db, job_id),
    )
    generator = LLMInsightGenerator(
        api_key=settings.ANTHROPIC_API_KEY, model=settings.LLM_MODEL, max_tokens=settings.LLM_MAX_TOKENS,
    )
    summary = generator.generate_summary(context)

    update_job_status(db, job_id, "generating_report", 94)
    pdf_path = generate_pdf_report(
        job_id=job_id,
        video_name=video.original_name,
        behaviour_distribution=get_behaviour_distribution(db, job_id),
        purchase_intent_summary=get_purchase_intent_summary(db, job_id),
        zone_summaries=get_zone_summaries(db, job_id),
        recommendations=get_recommendations_dicts(db, job_id),
        llm_summary=summary,
    )
    db.add(Report(job_id=job_id, file_path=pdf_path, summary=summary, llm_insights=summary))
    db.commit()

    update_job_status(db, job_id, "completed", 100)
    return "completed"


# ── FastAPI BackgroundTask runner (no Celery/Redis required) ──────────────────

def run_pipeline_for_job(job_id: str) -> None:
    """
    Entry point for FastAPI BackgroundTasks. Creates its own DB session so
    it can run after the HTTP response has already been sent.
    """
    db = SessionLocal()
    try:
        _execute(job_id, db)
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        update_job_status(db, job_id, "failed", 0, error_message=str(exc))
    finally:
        db.close()


# ── Celery task (for deployments with a real Redis broker) ───────────────────

@celery_app.task(name="app.tasks.pipeline_task.process_video_job", bind=True)
def process_video_job(self, job_id: str) -> str:
    db = SessionLocal()
    try:
        return _execute(job_id, db)
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        update_job_status(db, job_id, "failed", 0, error_message=str(exc))
        raise
    finally:
        db.close()
