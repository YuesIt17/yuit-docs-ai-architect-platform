"""FastAPI dependencies shared by routers."""

from __future__ import annotations

from typing import Annotated

from fastapi import Header, HTTPException

from kp.config import get_settings
from kp.deps import AppContainer, get_container
from kp.security.rbac import AuthDisabledError, resolve_principal
from pipelines.seed_all import seed_store


def principal_dep(authorization: Annotated[str | None, Header()] = None):
    settings = get_settings()
    try:
        return resolve_principal(authorization, demo_auth_enabled=settings.demo_auth_enabled)
    except AuthDisabledError as exc:
        raise HTTPException(
            status_code=401,
            detail="Demo auth disabled and real IdP is not configured",
        ) from exc


def container_dep() -> AppContainer:
    c = get_container()
    if not c._seeded:
        seed_store(c.store)
    return c
