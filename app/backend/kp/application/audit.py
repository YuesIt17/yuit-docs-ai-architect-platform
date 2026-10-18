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
