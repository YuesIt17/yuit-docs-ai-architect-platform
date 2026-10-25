"""Health: liveness stays cheap; readiness reflects mandatory live deps."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response

from kp.api.deps import container_dep
from kp.config import Settings, get_settings
from kp.deps import AppContainer
from kp.domain.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
@router.get("/healthz", response_model=HealthResponse)
async def liveness(settings: Settings = Depends(get_settings), c: AppContainer = Depends(container_dep)):
    """Liveness: process is up. Does not fail on DB so kube won't restart-storm."""
    probe = await c.llm.probe()
    cfg = c.llm.get_config()
    return HealthResponse(
        status="ok",
        store_backend=settings.store_backend,
        llm_provider=cfg.provider,
        llm_model=cfg.model,
        llm_reachable=probe.get("reachable"),
        index_version=settings.index_version,
    )


@router.get("/ready", response_model=HealthResponse)
@router.get("/readyz", response_model=HealthResponse)
async def readiness(
    response: Response,
    settings: Settings = Depends(get_settings),
    c: AppContainer = Depends(container_dep),
):
    """Readiness: when STORE_BACKEND=live + strict, require Neo4j/Qdrant."""
    probe = await c.llm.probe()
    cfg = c.llm.get_config()
    status = "ok"
    if settings.store_backend == "live" and settings.store_strict_live:
        live = bool(getattr(c.store, "live_enabled", False))
        if not live:
            status = "degraded"
            response.status_code = 503
    return HealthResponse(
        status=status,
        store_backend=settings.store_backend,
        llm_provider=cfg.provider,
        llm_model=cfg.model,
        llm_reachable=probe.get("reachable"),
        index_version=settings.index_version,
    )


@router.get("/v1/graph/stats")
async def graph_stats(c: AppContainer = Depends(container_dep)):
    return c.store.graph_stats()
