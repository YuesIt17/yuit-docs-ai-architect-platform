"""Request audit trail + latency / token metrics."""

from __future__ import annotations

import time

from kp.config import Settings
from kp.deps import AppContainer
from kp.observability import metrics


def record_request_audit(
    c: AppContainer,
    settings: Settings,
    request_id: str,
    principal,
    state: dict,
    started: float,
    modality: str,
) -> None:
    """Append an audit row and update RAG / ACL / token Prometheus metrics.

    Args:
        c: App DI container.
        settings: Runtime settings (index/policy versions).
        request_id: Correlation id for the HTTP request.
        principal: Authenticated demo principal.
        state: Final agent state dict.
        started: perf_counter() at request start.
        modality: chat | label.
    """
    latency = int((time.perf_counter() - started) * 1000)
    metrics.RAG_LATENCY.observe(latency)
    tin = int(state.get("tokens_in") or 0)
    tout = int(state.get("tokens_out") or 0)
    agent_id = str(state.get("agent_id") or settings.default_agent_id)
    team_id = str(state.get("team_id") or settings.llm_team_id)
    gateway = str(state.get("gateway") or c.llm.get_config().gateway)
    if tin:
        metrics.LLM_TOKENS.labels(direction="in").inc(tin)
        metrics.LLM_TOKENS_ATTRIBUTED.labels(
            direction="in", agent_id=agent_id, team=team_id, gateway=gateway
        ).inc(tin)
    if tout:
        metrics.LLM_TOKENS.labels(direction="out").inc(tout)
        metrics.LLM_TOKENS_ATTRIBUTED.labels(
            direction="out", agent_id=agent_id, team=team_id, gateway=gateway
        ).inc(tout)
    if state.get("acl_decision", "").startswith("deny"):
        metrics.ACL_DENIES.labels(role=principal.role).inc()
    if state.get("acl_decision") == "deny_kill_switch":
        metrics.KILL_SWITCH_BLOCKS.labels(agent_id=agent_id).inc()
    c.store.audit.append(
        {
            "request_id": request_id,
            "trace_id": state.get("trace_id"),
            "user_id": principal.user_id,
            "role": principal.role,
            "modality": modality,
            "agent_id": agent_id,
            "team_id": team_id,
            "gateway": gateway,
            "model_route": state.get("model_route"),
            "prompt_version": state.get("prompt_version") or settings.prompt_version,
            "flag_variant": state.get("flag_variant"),
            "model_uri": state.get("model_uri"),
            "index_version": settings.index_version,
            "policy_version": settings.policy_version,
            "tokens_in": tin,
            "tokens_out": tout,
            "tokens_estimated": state.get("acl_decision") != "allow_cache"
            and (
                # Mark word-split estimates when serving did not return usage
                tin > 0 and state.get("tokens_source") != "serving"
            ),
            "cost_est": round((tin + tout) * 0.000002, 6),
            "acl_decision": state.get("acl_decision", "allow"),
            "degraded": state.get("degraded", False),
            "latency_ms": latency,
        }
    )
