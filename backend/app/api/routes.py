from __future__ import annotations

import json
import time
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Header, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from app.config import Settings, get_settings
from app.deps import AppContainer, get_container
from app.models.schemas import (
    ChatRequest,
    ChatResponse,
    Citation,
    HealthResponse,
    JobCreateRequest,
    JobResponse,
    LabelExtract,
    LabelResponse,
    PresignResponse,
)
from app.security.rbac import resolve_principal
from app.security.guardrails import vision_input_guard
from app.services.cache import CacheEntry
from app.services.knowledge_store import DocumentNode, LabelAssetNode
from app.services import metrics
from pipelines.seed_all import seed_store

router = APIRouter()


def principal_dep(authorization: Annotated[str | None, Header()] = None):
    return resolve_principal(authorization)


def container_dep() -> AppContainer:
    c = get_container()
    if not c._seeded:
        seed_store(c.store)
    return c


@router.get("/health", response_model=HealthResponse)
async def health(settings: Settings = Depends(get_settings), c: AppContainer = Depends(container_dep)):
    return HealthResponse(
        status="ok",
        store_backend=settings.store_backend,
        llm_provider=settings.llm_provider,
        index_version=settings.index_version,
    )


@router.get("/v1/graph/stats")
async def graph_stats(c: AppContainer = Depends(container_dep)):
    return c.store.graph_stats()


@router.post("/v1/chat", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    principal=Depends(principal_dep),
    c: AppContainer = Depends(container_dep),
    settings: Settings = Depends(get_settings),
):
    started = time.perf_counter()
    request_id = str(uuid.uuid4())
    session_id = body.session_id or str(uuid.uuid4())

    cached = c.cache.get(body.message, principal.role, settings.index_version)
    if cached:
        metrics.CACHE_HIT_RATE.set(c.cache.hit_rate)
        metrics.REQUESTS.labels(endpoint="chat", status="cache").inc()
        return ChatResponse(
            answer=cached.answer,
            citations=[Citation(**x) for x in cached.citations],
            session_id=session_id,
            request_id=request_id,
            acl_decision="allow_cache",
            model_uri="cache://semantic",
            index_version=settings.index_version,
        )

    if body.stream:
        async def event_stream():
            state = await c.agent.arun(
                {
                    "request_id": request_id,
                    "message": body.message,
                    "modality": "chat",
                    "role": principal.role,
                    "user_id": principal.user_id,
                    "errors": [],
                }
            )
            # SSE: meta then final
            yield f"event: meta\ndata: {json.dumps({'request_id': request_id, 'session_id': session_id})}\n\n"
            payload = {
                "answer": state.get("answer", ""),
                "citations": state.get("citations") or [],
                "degraded": state.get("degraded", False),
                "acl_decision": state.get("acl_decision", "allow"),
            }
            yield f"event: final\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
            _audit(c, settings, request_id, principal, state, started, "chat")

        metrics.REQUESTS.labels(endpoint="chat", status="stream").inc()
        return StreamingResponse(event_stream(), media_type="text/event-stream")

    state = await c.agent.arun(
        {
            "request_id": request_id,
            "message": body.message,
            "modality": "chat",
            "role": principal.role,
            "user_id": principal.user_id,
            "errors": [],
        }
    )
    _audit(c, settings, request_id, principal, state, started, "chat")
    citations = [Citation(**x) for x in state.get("citations") or []]
    if state.get("acl_decision") == "allow":
        c.cache.put(
            body.message,
            principal.role,
            CacheEntry(
                answer=state.get("answer", ""),
                citations=state.get("citations") or [],
                index_version=settings.index_version,
            ),
        )
    metrics.CACHE_HIT_RATE.set(c.cache.hit_rate)
    metrics.REQUESTS.labels(endpoint="chat", status=state.get("acl_decision", "allow")).inc()
    return ChatResponse(
        answer=state.get("answer", ""),
        citations=citations,
        session_id=session_id,
        request_id=request_id,
        degraded=state.get("degraded", False),
        acl_decision=state.get("acl_decision", "allow"),
        model_uri=state.get("model_uri"),
        index_version=settings.index_version,
    )


@router.post("/v1/vision/label", response_model=LabelResponse)
async def vision_label(
    file: UploadFile = File(...),
    page_limit: int = 3,
    principal=Depends(principal_dep),
    c: AppContainer = Depends(container_dep),
    settings: Settings = Depends(get_settings),
):
    started = time.perf_counter()
    request_id = str(uuid.uuid4())
    data = await file.read()
    guard = vision_input_guard(file.filename or "upload.bin", file.content_type, len(data))
    if not guard.ok:
        metrics.REQUESTS.labels(endpoint="vision", status="guard_deny").inc()
        raise HTTPException(status_code=400, detail={"reasons": guard.reasons})

    asset_id = str(uuid.uuid4())
    etag = c.object_store.content_hash(data)
    vision = c.vision.recognize(file.filename or "label.png", data, page_limit=page_limit)

    s3_raw = c.object_store.put_bytes("raw", asset_id, file.filename or f"label.{vision.source_format}", data, file.content_type or "application/octet-stream")
    for i, page in enumerate(vision.page_images_png):
        c.object_store.put_bytes("normalized", asset_id, f"page-{i}.png", page, "image/png")
    extract = {
        "brand": vision.brand,
        "barcode": vision.barcode,
        "net_weight": vision.net_weight,
        "ingredients": vision.ingredients,
        "allergens": vision.allergens,
        "pages_processed": vision.page_count,
        "confidence": vision.confidence,
        "raw_ocr_text": vision.ocr_text,
    }
    s3_rec = c.object_store.put_json("recognized", asset_id, "extract.json", extract)
    c.object_store.put_json(
        "exports",
        asset_id,
        "pim_payload.json",
        {"asset_id": asset_id, "extract": extract, "schema_version": "1.0", "index_version": settings.index_version},
    )

    # Index OCR into GraphRAG
    doc_id = f"label-{asset_id[:8]}"
    c.store.upsert_document(
        DocumentNode(
            doc_id=doc_id,
            title=f"Label {vision.brand or asset_id[:8]}",
            corpus="product",
            classification="internal",
            allowed_roles=["store_associate", "category_manager", "compliance_officer"],
            text=vision.ocr_text,
            metadata={"modality": "ocr", "asset_id": asset_id},
        )
    )
    for a in vision.allergens:
        c.store.upsert_entity(a, "allergen", [doc_id])
    if vision.brand:
        c.store.upsert_entity(vision.brand, "brand", [doc_id])

    c.store.add_label_asset(
        LabelAssetNode(
            asset_id=asset_id,
            source_format=vision.source_format,
            page_count=vision.page_count,
            classification="internal",
            s3_uri_raw=s3_raw,
            s3_uri_recognized=s3_rec,
            s3_uri_normalized=f"s3://{settings.minio_bucket}/normalized/{asset_id}/",
            etag=etag,
            extract=extract,
        )
    )
    c.store.push_outbox(
        "label.recognized",
        {"asset_id": asset_id, "s3_uri_recognized": s3_rec, "s3_uri_raw": s3_raw, "schema_version": "1.0"},
    )

    state = await c.agent.arun(
        {
            "request_id": request_id,
            "message": f"Analyze label allergens {', '.join(vision.allergens)}",
            "modality": "label",
            "role": principal.role,
            "user_id": principal.user_id,
            "label_extract": extract,
            "errors": [],
        }
    )
    latency = int((time.perf_counter() - started) * 1000)
    metrics.VISION_LATENCY.observe(latency)
    _audit(c, settings, request_id, principal, state, started, "label")
    metrics.REQUESTS.labels(endpoint="vision", status="ok").inc()

    warnings = []
    if vision.allergens:
        warnings.append(f"Detected allergens: {', '.join(vision.allergens)}")
    return LabelResponse(
        asset_id=asset_id,
        extract=LabelExtract(**{**extract, "pages_processed": vision.page_count}),
        warnings=warnings,
        citations=[Citation(**x) for x in state.get("citations") or []],
        answer=state.get("answer", ""),
        s3_uri_raw=s3_raw,
        s3_uri_recognized=s3_rec,
        request_id=request_id,
        degraded=state.get("degraded", False),
    )


@router.get("/v1/assets/{asset_id}/presign", response_model=PresignResponse)
async def presign_asset(
    asset_id: str,
    kind: str = "recognized",
    principal=Depends(principal_dep),
    c: AppContainer = Depends(container_dep),
):
    asset = c.store.labels.get(asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="asset not found")
    if asset.classification == "secret" and principal.role != "compliance_officer":
        metrics.ACL_DENIES.labels(role=principal.role).inc()
        raise HTTPException(status_code=403, detail="ACL deny")
    uri = {
        "raw": asset.s3_uri_raw,
        "recognized": asset.s3_uri_recognized,
        "normalized": asset.s3_uri_normalized,
    }.get(kind)
    if not uri:
        raise HTTPException(status_code=400, detail="unknown kind")
    url = c.object_store.presign(uri if kind != "normalized" else f"{uri}page-0.png")
    return PresignResponse(asset_id=asset_id, kind=kind, url=url, expires_seconds=300)  # type: ignore[arg-type]


@router.post("/v1/jobs", response_model=JobResponse, status_code=202)
async def create_job(body: JobCreateRequest, c: AppContainer = Depends(container_dep)):
    job_id = c.store.create_job(body.job_type, body.payload)
    # MVP: complete immediately for demo
    c.store.complete_job(job_id, {"ok": True, "echo": body.payload})
    return JobResponse(job_id=job_id, status="completed", result={"ok": True, "echo": body.payload})


@router.get("/v1/jobs/{job_id}", response_model=JobResponse)
async def get_job(job_id: str, c: AppContainer = Depends(container_dep)):
    job = c.store.jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    return JobResponse(job_id=job_id, status=job["status"], result=job.get("result"))


@router.get("/v1/outbox")
async def outbox(c: AppContainer = Depends(container_dep), principal=Depends(principal_dep)):
    if principal.role not in {"category_manager", "compliance_officer"}:
        raise HTTPException(status_code=403, detail="ACL deny")
    return {"events": c.store.outbox[-50:]}


def _audit(c: AppContainer, settings: Settings, request_id: str, principal, state: dict, started: float, modality: str) -> None:
    latency = int((time.perf_counter() - started) * 1000)
    metrics.RAG_LATENCY.observe(latency)
    tin = int(state.get("tokens_in") or 0)
    tout = int(state.get("tokens_out") or 0)
    if tin:
        metrics.LLM_TOKENS.labels(direction="in").inc(tin)
    if tout:
        metrics.LLM_TOKENS.labels(direction="out").inc(tout)
    if state.get("acl_decision", "").startswith("deny"):
        metrics.ACL_DENIES.labels(role=principal.role).inc()
    c.store.audit.append(
        {
            "request_id": request_id,
            "user_id": principal.user_id,
            "role": principal.role,
            "modality": modality,
            "model_uri": state.get("model_uri"),
            "index_version": settings.index_version,
            "policy_version": settings.policy_version,
            "tokens_in": tin,
            "tokens_out": tout,
            "cost_est": round((tin + tout) * 0.000002, 6),
            "acl_decision": state.get("acl_decision", "allow"),
            "degraded": state.get("degraded", False),
            "latency_ms": latency,
        }
    )
