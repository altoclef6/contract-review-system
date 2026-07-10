from celery import Celery

from contract_review.core.config import get_settings

settings = get_settings()
celery_app = Celery(
    "contract_review",
    broker=settings.celery_broker_url.get_secret_value(),
    backend=settings.celery_result_backend.get_secret_value(),
    include=["contract_review.tasks.jobs"],
)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=900,
    beat_schedule={
        "contract-expiration-reminders": {
            "task": "contract_review.send_expiration_reminders",
            "schedule": 86400.0,
        }
    },
)
