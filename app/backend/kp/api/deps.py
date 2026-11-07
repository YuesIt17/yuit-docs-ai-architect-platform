"""FastAPI dependencies shared by routers."""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from fastapi import Header, HTTPException

from kp.config import get_settings
from kp.deps import AppContainer, get_container
from kp.security.rbac import (
    AuthDisabledError,
    AuthError,
    AuthUnavailableError,
    JwksCache,
    OidcVerifier,
    UnknownRoleError,
    resolve_principal,
)
from pipelines.seed_all import seed_store

_UNAUTHENTICATED = {"WWW-Authenticate": "Bearer"}


@lru_cache
def get_oidc_verifier() -> OidcVerifier | None:
    settings = get_settings()
    if not settings.oidc_issuer:
        return None
    jwks_url = settings.oidc_jwks_url or f"{settings.oidc_issuer.rstrip('/')}/protocol/openid-connect/certs"
    return OidcVerifier(
        issuer=settings.oidc_issuer,
        audience=settings.oidc_audience,
        algorithms=settings.oidc_algorithm_list,
        jwks=JwksCache(jwks_url),
    )


# A plain `def`: FastAPI runs it in the threadpool, so a JWKS fetch does not block the event loop.
def principal_dep(authorization: Annotated[str | None, Header()] = None):
    settings = get_settings()
    try:
        return resolve_principal(
            authorization,
            demo_auth_enabled=settings.demo_auth_enabled,
            verifier=get_oidc_verifier(),
        )
    except AuthDisabledError as exc:
        raise HTTPException(
            status_code=401,
            detail="Demo auth disabled and real IdP is not configured",
            headers=_UNAUTHENTICATED,
        ) from exc
    except AuthError as exc:
        raise HTTPException(status_code=401, detail="Invalid or missing token", headers=_UNAUTHENTICATED) from exc
    except UnknownRoleError as exc:
        raise HTTPException(status_code=403, detail="The account has no platform role") from exc
    except AuthUnavailableError as exc:
        raise HTTPException(status_code=503, detail="Token validation is temporarily unavailable") from exc


def container_dep() -> AppContainer:
    c = get_container()
    if not c._seeded:
        seed_store(c.store)
    return c
