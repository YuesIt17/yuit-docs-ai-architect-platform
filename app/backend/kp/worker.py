"""Celery worker for catalog ingest. Run: celery -A kp.worker worker --concurrency=2"""

from __future__ import annotations

from celery import Celery

from kp.application.jobs import run_celery_ingest
from kp.config import get_settings
from kp.deps import get_container

settings = get_settings()
celery_app = Celery("kp", broker=settings.redis_url)
celery_app.conf.update(
    # Redeliver a job if a worker dies mid-catalog. Upserts make the repeat safe.
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    # Embedding is CPU heavy and catalogs are long, so workers take one task at a time.
    worker_prefetch_multiplier=1,
    task_ignore_result=True,
    task_serializer="json",
    accept_content=["json"],
    broker_connection_retry_on_startup=True,
)


@celery_app.task(name="kp.ingest_documents")
def ingest_documents(job_id: str, documents: list[dict]) -> dict:
    import redis

    return run_celery_ingest(
        get_container().store,
        redis.Redis.from_url(settings.redis_url, decode_responses=True),
        job_id,
        documents,
    )
