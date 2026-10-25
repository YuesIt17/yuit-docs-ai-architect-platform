"""Vision / asset HTTP routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from kp.api.deps import container_dep, principal_dep
from kp.application.vision import VisionServiceApp
from kp.config import Settings, get_settings
from kp.deps import AppContainer
from kp.domain.schemas import LabelResponse, PresignResponse
from kp.observability import metrics
from kp.security.guardrails import MAX_UPLOAD_BYTES
from kp.security.rbac import can_access

router = APIRouter(tags=["vision"])

# Presigned URL TTL. Already-issued URLs remain valid until expiry; immediate
# revoke requires object deletion or a separate short-lived token store (planned).
PRESIGN_EXPIRES_SECONDS = 300


@router.post("/v1/vision/label", response_model=LabelResponse)
async def vision_label(
    file: UploadFile = File(...),
    page_limit: int = 3,
    principal=Depends(principal_dep),
    c: AppContainer = Depends(container_dep),
    settings: Settings = Depends(get_settings),
):
    if page_limit < 1 or page_limit > 10:
        raise HTTPException(status_code=400, detail="page_limit must be 1..10")
    # Bound body size while reading (not only after full upload into memory).
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=400, detail={"reasons": ["file_too_large"]})
        chunks.append(chunk)
    data = b"".join(chunks)
    return await VisionServiceApp(c, settings).recognize_label(
        filename=file.filename or "upload.bin",
        content_type=file.content_type,
        data=data,
        page_limit=page_limit,
        principal=principal,
    )


@router.get("/v1/assets/{asset_id}/presign", response_model=PresignResponse)
async def presign_asset(
    asset_id: str,
    kind: str = "recognized",
    principal=Depends(principal_dep),
    c: AppContainer = Depends(container_dep),
):
    """Issue a short-lived download URL. Access uses the same can_access policy as RAG."""
    asset = c.store.labels.get(asset_id)
    if not asset:
        # Do not leak existence vs authorization via different codes for unknown ids —
        # still 404 for missing; ACL deny is 403 when known but forbidden.
        raise HTTPException(status_code=404, detail="asset not found")
    allowed_roles = getattr(asset, "allowed_roles", None)
    if not can_access(principal, asset.classification, allowed_roles):
        metrics.ACL_DENIES.labels(role=principal.role).inc()
        raise HTTPException(status_code=403, detail="ACL deny")
    uri = {
        "raw": asset.s3_uri_raw,
        "recognized": asset.s3_uri_recognized,
        "normalized": asset.s3_uri_normalized,
    }.get(kind)
    if not uri:
        raise HTTPException(status_code=400, detail="unknown kind")
    url = c.object_store.presign(
        uri if kind != "normalized" else f"{uri.rstrip('/')}/page-0.png",
        expires_seconds=PRESIGN_EXPIRES_SECONDS,
    )
    return PresignResponse(
        asset_id=asset_id,
        kind=kind,  # type: ignore[arg-type]
        url=url,
        expires_seconds=PRESIGN_EXPIRES_SECONDS,
    )
