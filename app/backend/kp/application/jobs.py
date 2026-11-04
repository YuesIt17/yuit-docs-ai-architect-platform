"""Background ingest of document catalogs: in-process for dev, Celery for the live stack."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Any

from kp.domain.nodes import DocumentNode
from kp.domain.schemas import IngestDocument, IngestRequest

logger = logging.getLogger("kp.jobs")

STATUS_KEY = "kp:jobs:{job_id}"
STATUS_TTL_SECONDS = 7 * 24 * 3600
# A Celery worker writes to Neo4j and Qdrant, but each API replica also keeps an in-memory
# mirror, which ACL re-checks read. Replicas follow this stream to learn about new documents.
MIRROR_STREAM = "kp:ingested-documents"
MIRROR_MAX_LEN = 100_000
_MIRROR_BLOCK_MS = 5000


def ingest_one(store, item: IngestDocument, *, strict: bool = False) -> DocumentNode:
    doc = DocumentNode(
        doc_id=item.doc_id,
        title=item.title,
        corpus=item.corpus,
        classification=item.classification,
        allowed_roles=item.allowed_roles,
        text=item.text,
    )
    store.upsert_document(doc, raise_on_live_error=strict)
    for entity in item.entities:
        store.upsert_entity(entity.name, entity.type, [doc.doc_id])
    for topic in item.topics:
        store.link_topic(topic, doc.doc_id)
    return doc


def finished_status(ingested: int, failed: list[dict[str, str]]) -> dict[str, Any]:
    """Partial success is reported, so one bad document does not hide the rest or look like success."""
    return {
        "status": "failed" if failed and not ingested else "completed",
        "result": {"ingested": ingested, "failed": failed},
    }


def run_celery_ingest(store, redis_client, job_id: str, documents: list[dict[str, Any]]) -> dict[str, Any]:
    """Task body for the Celery worker."""
    write_status(redis_client, job_id, {"status": "running", "result": None})
    ingested = 0
    failed: list[dict[str, str]] = []
    for raw in documents:
        item = IngestDocument.model_validate(raw)
        try:
            ingest_one(store, item, strict=True)
            redis_client.xadd(MIRROR_STREAM, {"doc": item.model_dump_json()}, maxlen=MIRROR_MAX_LEN, approximate=True)
            ingested += 1
        except Exception as exc:  # One bad document must not abort a long catalog load.
            logger.warning("ingest failed for %s: %s", item.doc_id, exc)
            failed.append({"doc_id": item.doc_id, "error": exc.__class__.__name__})
    status = finished_status(ingested, failed)
    write_status(redis_client, job_id, status)
    return status


def write_status(redis_client, job_id: str, status: dict[str, Any]) -> None:
    redis_client.set(STATUS_KEY.format(job_id=job_id), json.dumps(status), ex=STATUS_TTL_SECONDS)


class InlineJobQueue:
    """Dev and CI: runs on the event loop and yields between documents.

    Not in a thread: retrieval iterates the same in-memory dicts this writes to.
    """

    def __init__(self, store):
        self.store = store
        self._tasks: set[asyncio.Task] = set()

    async def submit(self, request: IngestRequest) -> str:
        job_id = self.store.create_job("ingest_documents", {"documents": len(request.documents)})
        task = asyncio.create_task(self._run(job_id, request))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return job_id

    async def _run(self, job_id: str, request: IngestRequest) -> None:
        job = self.store.jobs[job_id]
        job["status"] = "running"
        ingested = 0
        failed: list[dict[str, str]] = []
        for item in request.documents:
            try:
                ingest_one(self.store, item, strict=True)
                ingested += 1
            except Exception as exc:  # Same contract as the Celery path.
                failed.append({"doc_id": item.doc_id, "error": exc.__class__.__name__})
            await asyncio.sleep(0)
        job.update(finished_status(ingested, failed))

    def get(self, job_id: str) -> dict[str, Any] | None:
        return self.store.jobs.get(job_id)


class CeleryJobQueue:
    def __init__(self, redis_client):
        self.redis = redis_client

    async def submit(self, request: IngestRequest) -> str:
        from kp.worker import ingest_documents

        job_id = str(uuid.uuid4())
        write_status(self.redis, job_id, {"status": "queued", "result": None})
        documents = [item.model_dump() for item in request.documents]
        await asyncio.to_thread(ingest_documents.delay, job_id, documents)
        return job_id

    def get(self, job_id: str) -> dict[str, Any] | None:
        raw = self.redis.get(STATUS_KEY.format(job_id=job_id))
        return json.loads(raw) if raw else None


def apply_mirror_entries(store, entries) -> str | None:
    """Add stream entries to this replica's in-memory mirror. Returns the last processed id."""
    last_id = None
    for entry_id, fields in entries:
        item = IngestDocument.model_validate_json(fields["doc"])
        store.mirror_document(
            DocumentNode(
                doc_id=item.doc_id,
                title=item.title,
                corpus=item.corpus,
                classification=item.classification,
                allowed_roles=item.allowed_roles,
                text=item.text,
            )
        )
        last_id = entry_id
    return last_id


async def follow_mirror_stream(store, redis_client) -> None:
    """Replay from the start, so a restarted replica recovers every worker-ingested document."""
    last_id = "0"
    while True:
        try:
            batches = await asyncio.to_thread(
                redis_client.xread, {MIRROR_STREAM: last_id}, count=100, block=_MIRROR_BLOCK_MS
            )
        except Exception as exc:  # Keep following through a Redis restart.
            logger.warning("mirror stream read failed: %s", exc)
            await asyncio.sleep(_MIRROR_BLOCK_MS / 1000)
            continue
        for _stream, entries in batches or []:
            last_id = apply_mirror_entries(store, entries) or last_id
