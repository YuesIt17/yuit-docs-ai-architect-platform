"""FastAPI dependencies shared by routers."""

from __future__ import annotations

from typing import Annotated

from fastapi import Header

from kp.deps import AppContainer, get_container
from kp.security.rbac import resolve_principal
from pipelines.seed_all import seed_store


def principal_dep(authorization: Annotated[str | None, Header()] = None):
    return resolve_principal(authorization)


def container_dep() -> AppContainer:
    c = get_container()
    if not c._seeded:
        seed_store(c.store)
    return c
