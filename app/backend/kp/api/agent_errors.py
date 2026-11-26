"""Map agent registry exceptions to HTTP errors."""

from __future__ import annotations

from fastapi import HTTPException

from kp.agents.registry import (
    AgentConflictError,
    AgentDisabledError,
    AgentKillSwitchError,
    AgentManifestInvalidError,
    AgentNotFoundError,
    AgentRoleDeniedError,
)


def http_from_registry(exc: Exception) -> HTTPException:
    if isinstance(exc, AgentNotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, AgentKillSwitchError):
        return HTTPException(status_code=503, detail=str(exc))
    if isinstance(exc, AgentDisabledError):
        return HTTPException(status_code=503, detail=str(exc))
    if isinstance(exc, AgentRoleDeniedError):
        return HTTPException(status_code=403, detail=str(exc))
    if isinstance(exc, AgentConflictError):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, AgentManifestInvalidError):
        return HTTPException(status_code=422, detail=str(exc))
    return HTTPException(status_code=500, detail="agent registry error")
