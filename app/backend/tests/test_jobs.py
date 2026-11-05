"""Background ingest: access control, real status, partial failure and replica mirroring."""

from __future__ import annotations

import asyncio
import os

import pytest
from fastapi.testclient import TestClient

from kp.application.jobs import (
    MIRROR_STREAM,
    CeleryJobQueue,
    InlineJobQueue,
    apply_mirror_entries,
    run_celery_ingest,
)
from kp.deps import get_container
from kp.domain.schemas import IngestDocument, IngestRequest
from kp.main import app
from kp.security.rbac import Principal


def document(doc_id: str = "cat-001", text: str = "Catalog rule about xylitol labeling.") -> dict:
    return {
        "doc_id": doc_id,
        "title": "Catalog rule",
        "corpus": "regulatory",
        "classification": "internal",
        "allowed_roles": ["compliance_officer"],
        "text": text,
    }


class FakeRedis:
    def __init__(self):
        self.values, self.streams = {}, {}

    def set(self, key, value, ex=None):
        self.values[key] = value

    def get(self, key):
        return self.values.get(key)

    def xadd(self, stream, fields, maxlen=None, approximate=None):
        entries = self.streams.setdefault(stream, [])
        entries.append((f"{len(entries) + 1}-0", fields))


@pytest.fixture
def client():
    get_container.cache_clear()
    with TestClient(app) as test_client:
        yield test_client


def bearer(role: str) -> dict:
    return {"Authorization": f"Bearer {role}"}


def post_ingest(client, role: str, documents: list[dict]):
    body = {"job_type": "ingest_documents", "payload": {"documents": documents}}
    return client.post("/v1/jobs", json=body, headers=bearer(role))


@pytest.mark.parametrize("role", ["guest", "associate", "manager"])
def test_only_compliance_can_ingest(client, role):
    assert post_ingest(client, role, [document()]).status_code == 403
    assert "cat-001" not in get_container().store.documents


def test_jobs_require_authentication(client):
    body = {"job_type": "ingest_documents", "payload": {"documents": [document()]}}
    assert client.post("/v1/jobs", json=body).status_code in {401, 403}


def test_invalid_payload_is_rejected(client):
    bad = {**document(), "classification": "top-secret"}
    assert post_ingest(client, "compliance", [bad]).status_code == 422


def test_catalog_size_is_limited(client):
    assert post_ingest(client, "compliance", [document(str(i)) for i in range(1001)]).status_code == 422


def test_ingest_makes_the_document_retrievable_with_its_acl(client):
    response = post_ingest(client, "compliance", [document()])
    assert response.status_code == 202
    assert response.json()["status"] in {"queued", "running", "completed"}
    status = client.get(f"/v1/jobs/{response.json()['job_id']}", headers=bearer("compliance")).json()
    assert status["status"] == "completed"
    assert status["result"] == {"ingested": 1, "failed": []}

    store = get_container().store
    officer = Principal(user_id="c", role="compliance_officer")
    associate = Principal(user_id="a", role="store_associate")
    assert any(h.document.doc_id == "cat-001" for h in store.hybrid_retrieve("xylitol labeling", officer, top_k=5))
    hits = store.hybrid_retrieve("xylitol labeling", associate, top_k=5)
    assert not any(h.document.doc_id == "cat-001" for h in hits)


class FlakyStore:
    """Fails for one document, as a live store outage would."""

    def __init__(self):
        self.saved, self.mirrored = [], []
        self.jobs = {}

    def upsert_document(self, doc, raise_on_live_error=False):
        if doc.doc_id == "bad":
            raise ConnectionError("neo4j down")
        self.saved.append(doc.doc_id)

    def upsert_entity(self, *args):
        pass

    def link_topic(self, *args):
        pass

    def create_job(self, job_type, request):
        self.jobs["j"] = {"job_id": "j", "status": "queued", "result": None}
        return "j"

    def mirror_document(self, doc):
        self.mirrored.append(doc.doc_id)


def test_worker_reports_partial_failure_and_continues():
    redis_client = FakeRedis()
    status = run_celery_ingest(FlakyStore(), redis_client, "j", [document("a"), document("bad"), document("b")])
    assert status["status"] == "completed"
    assert status["result"]["ingested"] == 2
    assert status["result"]["failed"] == [{"doc_id": "bad", "error": "ConnectionError"}]


def test_all_documents_failing_marks_the_job_failed():
    status = run_celery_ingest(FlakyStore(), FakeRedis(), "j", [document("bad")])
    assert status["status"] == "failed"


def test_failed_document_is_not_mirrored_to_api_replicas():
    redis_client = FakeRedis()
    store = FlakyStore()
    run_celery_ingest(store, redis_client, "j", [document("a"), document("bad")])
    last_id = apply_mirror_entries(store, redis_client.streams[MIRROR_STREAM])
    assert store.mirrored == ["a"]
    assert last_id == "1-0"


@pytest.mark.asyncio
async def test_inline_queue_reports_partial_failure():
    store = FlakyStore()
    queue = InlineJobQueue(store)
    documents = [IngestDocument(**document("bad")), IngestDocument(**document("a"))]
    job_id = await queue.submit(IngestRequest(documents=documents))
    await asyncio.gather(*queue._tasks)
    assert queue.get(job_id)["result"]["ingested"] == 1
    assert queue.get(job_id)["result"]["failed"][0]["doc_id"] == "bad"


@pytest.mark.asyncio
async def test_celery_queue_records_status_before_enqueueing(monkeypatch):
    celery_worker = pytest.importorskip("kp.worker")
    sent = {}
    monkeypatch.setattr(
        celery_worker.ingest_documents, "delay", lambda job_id, docs: sent.update(job_id=job_id, docs=docs)
    )
    redis_client = FakeRedis()
    queue = CeleryJobQueue(redis_client)
    job_id = await queue.submit(IngestRequest(documents=[IngestDocument(**document())]))
    assert sent["job_id"] == job_id
    assert sent["docs"][0]["doc_id"] == "cat-001"
    assert queue.get(job_id)["status"] == "queued"


def test_worker_task_is_registered_and_late_acking():
    celery_worker = pytest.importorskip("kp.worker")
    assert "kp.ingest_documents" in celery_worker.celery_app.tasks
    assert celery_worker.celery_app.conf.task_acks_late is True


@pytest.mark.skipif(not os.environ.get("TEST_REDIS_URL"), reason="needs TEST_REDIS_URL")
def test_status_and_mirror_round_trip_on_real_redis():
    import redis

    client = redis.Redis.from_url(os.environ["TEST_REDIS_URL"], decode_responses=True)
    client.delete(MIRROR_STREAM)
    store = FlakyStore()
    run_celery_ingest(store, client, "real-redis", [document("a")])
    assert CeleryJobQueue(client).get("real-redis")["status"] == "completed"
    entries = client.xread({MIRROR_STREAM: "0"})[0][1]
    apply_mirror_entries(store, entries)
    assert store.mirrored == ["a"]
