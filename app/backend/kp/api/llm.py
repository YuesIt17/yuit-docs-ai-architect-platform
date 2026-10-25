"""LLM runtime config endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from kp.api.deps import container_dep, principal_dep
from kp.deps import AppContainer
from kp.domain.schemas import LLMConfigResponse, LLMConfigUpdate
from kp.infrastructure.llm import provider_presets
from kp.security.rbac import LLM_ADMIN_ROLES

router = APIRouter(prefix="/v1/llm", tags=["llm"])


def _config_response(c: AppContainer, probe: dict) -> LLMConfigResponse:
    cfg = c.llm.get_config()
    return LLMConfigResponse(
        provider=cfg.provider,
        base_url=cfg.base_url,
        model=cfg.model,
        model_uri=cfg.model_uri,
        reachable=probe.get("reachable"),
        detail=probe.get("detail"),
        presets=provider_presets(c.settings),
    )


@router.get("/config", response_model=LLMConfigResponse)
async def get_llm_config(
    principal=Depends(principal_dep),
    c: AppContainer = Depends(container_dep),
):
    return _config_response(c, await c.llm.probe())


@router.put("/config", response_model=LLMConfigResponse)
async def put_llm_config(
    body: LLMConfigUpdate,
    principal=Depends(principal_dep),
    c: AppContainer = Depends(container_dep),
):
    # Data-plane roles cannot change serving URL; only LLM admin roles.
    if principal.role not in LLM_ADMIN_ROLES:
        raise HTTPException(
            status_code=403,
            detail="ACL deny: only compliance_officer can change LLM serving config",
        )
    try:
        c.llm.apply_config(body.provider, body.base_url, body.model)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _config_response(c, await c.llm.probe())


@router.get("/health", response_model=LLMConfigResponse)
async def llm_health(c: AppContainer = Depends(container_dep)):
    return _config_response(c, await c.llm.probe())
