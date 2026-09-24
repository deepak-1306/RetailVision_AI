from app.models.user import User
from app.models.video import Video
from app.models.job import ProcessingJob, JobStatus
from app.models.behaviour import BehaviourEvent, BehaviourType
from app.models.prediction import PurchaseIntentPrediction
from app.models.recommendation import Recommendation
from app.models.report import Report

# Expose modules for `from app.models import user, video, ...`
from app.models import user, video, job, behaviour, prediction, recommendation, report

__all__ = [
    "User",
    "Video",
    "ProcessingJob",
    "JobStatus",
    "BehaviourEvent",
    "BehaviourType",
    "PurchaseIntentPrediction",
    "Recommendation",
    "Report",
    "user",
    "video",
    "job",
    "behaviour",
    "prediction",
    "recommendation",
    "report",
]
