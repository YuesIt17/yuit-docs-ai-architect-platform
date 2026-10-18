"""Vision / asset HTTP routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from kp.api.deps import container_dep, principal_dep
from kp.application.vision import VisionServiceApp
from kp.config import Settings, get_settings
from kp.deps import AppContainer
from kp.domain.schemas import LabelResponse, PresignResponse
from kp.observability import metrics

router = APIRouter(tags=["vision"])


@router.post("/v1/vision/label", response_model=LabelResponse)
async def vision_label(
    file: UploadFile = File(...),
    page_limit: int = 3,
    principal=Depends(principal_dep),
    c: AppContainer = Depends(container_dep),
    settings: Settings = Depends(get_settings),
):
    data = await file.read()
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
