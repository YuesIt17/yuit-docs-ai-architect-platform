"""Health and graph stats endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from kp.api.deps import container_dep
from kp.config import Settings, get_settings
from kp.deps import AppContainer
from kp.domain.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health(settings: Settings = Depends(get_settings), c: AppContainer = Depends(container_dep)):
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


@router.get("/v1/graph/stats")
async def graph_stats(c: AppContainer = Depends(container_dep)):
    return c.store.graph_stats()
