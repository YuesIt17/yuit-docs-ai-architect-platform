"""Jobs, audit, and outbox HTTP routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError

from kp.api.deps import container_dep, principal_dep
from kp.deps import AppContainer
from kp.domain.schemas import IngestRequest, JobCreateRequest, JobResponse

router = APIRouter(tags=["jobs"])


@router.get("/v1/audit")
async def audit_log(
    limit: int = 50,
    principal=Depends(principal_dep),
    c: AppContainer = Depends(container_dep),
):
    if principal.role not in {"category_manager", "compliance_officer"}:
        raise HTTPException(status_code=403, detail="ACL deny")
    rows = c.store.audit[-max(1, min(limit, 200)) :]
    return {"items": list(reversed(rows))}


@router.post("/v1/jobs", response_model=JobResponse, status_code=202)
async def create_job(
    body: JobCreateRequest,
    c: AppContainer = Depends(container_dep),
    principal=Depends(principal_dep),
):
    if body.job_type == "ingest_documents":
        # Ingest sets a document's classification, so it is limited to the role that owns classification.
        if principal.role != "compliance_officer":
            raise HTTPException(status_code=403, detail="ACL deny")
        try:
            request = IngestRequest.model_validate(body.payload)
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail=exc.errors(include_url=False, include_input=False)) from exc
        job_id = await c.jobs.submit(request)
        return JobResponse(job_id=job_id, status="queued", result=None)
    job_id = c.store.create_job(body.job_type, body.payload)
    c.store.complete_job(job_id, {"ok": True, "echo": body.payload})
    return JobResponse(job_id=job_id, status="completed", result={"ok": True, "echo": body.payload})


@router.get("/v1/jobs/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: str,
    c: AppContainer = Depends(container_dep),
    principal=Depends(principal_dep),
):
    job = c.jobs.get(job_id) or c.store.jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    return JobResponse(job_id=job_id, status=job["status"], result=job.get("result"))


@router.get("/v1/outbox")
async def outbox(c: AppContainer = Depends(container_dep), principal=Depends(principal_dep)):
    if principal.role not in {"category_manager", "compliance_officer"}:
        raise HTTPException(status_code=403, detail="ACL deny")
    return {"events": c.store.outbox[-50:]}
