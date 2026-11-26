"""Agent registry HTTP API — list, get, register, resolve, invoke."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from kp.agents.manifest import AgentManifest, ResolvedAgent
from kp.agents.registry import (
    AgentConflictError,
    AgentDisabledError,
    AgentKillSwitchError,
    AgentManifestInvalidError,
    AgentNotFoundError,
    AgentRoleDeniedError,
)
from kp.api.agent_errors import http_from_registry
from kp.api.deps import container_dep, principal_dep
from kp.application.chat import ChatService
from kp.config import Settings, get_settings
from kp.deps import AppContainer
from kp.domain.schemas import AgentSummary, ChatRequest, ChatResponse
from kp.security.rbac import LLM_ADMIN_ROLES, Principal

router = APIRouter(tags=["agents"])


@router.get("/v1/agents", response_model=list[AgentSummary])
async def list_agents(
    principal: Principal = Depends(principal_dep),
    c: AppContainer = Depends(container_dep),
):
    """List registered agents (disk manifests + API registrations)."""
    _ = principal
    return [
        AgentSummary(
            id=m.metadata.id,
            version=m.metadata.version,
            display_name=m.metadata.display_name,
            description=m.metadata.description,
            runtime=m.spec.runtime,
            enabled=m.spec.enabled,
            skills=[s.id for s in m.spec.skills],
            triggers=[t.type for t in m.spec.triggers if t.enabled],
        )
        for m in c.registry.list()
    ]


@router.get("/v1/agents/{agent_id}", response_model=AgentManifest)
async def get_agent(
    agent_id: str,
    principal: Principal = Depends(principal_dep),
    c: AppContainer = Depends(container_dep),
):
    _ = principal
    try:
        return c.registry.require(agent_id)
    except AgentNotFoundError as exc:
        raise http_from_registry(exc) from exc


@router.get("/v1/agents/{agent_id}/resolve", response_model=ResolvedAgent)
async def resolve_agent(
    agent_id: str,
    principal: Principal = Depends(principal_dep),
    c: AppContainer = Depends(container_dep),
    settings: Settings = Depends(get_settings),
):
    """Resolve live model / memory / tool bindings for an agent (practical debug view)."""
    try:
        c.registry.authorize(agent_id, principal.role)
        return c.registry.resolve(agent_id, settings, c.llm)
    except (AgentNotFoundError, AgentDisabledError, AgentRoleDeniedError) as exc:
        raise http_from_registry(exc) from exc


@router.post("/v1/agents", response_model=AgentManifest, status_code=201)
async def register_agent(
    body: AgentManifest,
    principal: Principal = Depends(principal_dep),
    c: AppContainer = Depends(container_dep),
):
    """Register an agent at runtime (in-memory; not persisted across restarts)."""
    if principal.role not in LLM_ADMIN_ROLES:
        raise HTTPException(status_code=403, detail="Only compliance_officer may register agents")
    try:
        return c.registry.register(body, source="api", overwrite=False)
    except (AgentConflictError, AgentManifestInvalidError) as exc:
        raise http_from_registry(exc) from exc


@router.post("/v1/agents/{agent_id}/invoke", response_model=ChatResponse)
async def invoke_agent(
    agent_id: str,
    body: ChatRequest,
    principal: Principal = Depends(principal_dep),
    c: AppContainer = Depends(container_dep),
    settings: Settings = Depends(get_settings),
):
    """Invoke a registered agent. LangGraph chat agents share the ChatService path."""
    try:
        manifest = c.registry.authorize(agent_id, principal.role)
    except (AgentNotFoundError, AgentDisabledError, AgentRoleDeniedError, AgentKillSwitchError) as exc:
        raise http_from_registry(exc) from exc

    if manifest.spec.runtime != "langgraph":
        raise HTTPException(
            status_code=501,
            detail=(
                f"agent {agent_id!r} runtime={manifest.spec.runtime!r} "
                "is not invokable via this endpoint yet; use its API trigger path"
            ),
        )

    # Force the resolved agent id (body.agent_id is ignored for path-based invoke).
    payload = body.model_copy(update={"agent_id": agent_id, "stream": False})
    try:
        result = await ChatService(c, settings).handle(payload, principal)
    except (
        AgentNotFoundError,
        AgentDisabledError,
        AgentRoleDeniedError,
        AgentKillSwitchError,
    ) as exc:
        raise http_from_registry(exc) from exc
    if isinstance(result, tuple) and result[0] == "stream":
        from fastapi.responses import StreamingResponse

        return StreamingResponse(result[1], media_type="text/event-stream")
    return result
