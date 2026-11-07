"""Authentication and RBAC for the RetailPartnerX Knowledge Platform.

Two modes exist, and `kp.config.Settings` refuses to start with both:

- Demo (`DEMO_AUTH_ENABLED=true`): the bearer value is a role name. For tests and the MOCK profile only.
- OIDC (`OIDC_ISSUER` set): the bearer value is a Keycloak access token, validated here on every request.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

import httpx
import jwt

ROLE_CLEARANCE: dict[str, set[str]] = {
    "guest": {"public"},
    "store_associate": {"public", "internal"},
    "category_manager": {"public", "internal"},
    "compliance_officer": {"public", "internal", "secret"},
}

# Roles allowed to change LLM serving config (admin-ish for MVP).
LLM_ADMIN_ROLES = frozenset({"compliance_officer"})

# When a user holds several platform roles, the first match wins, so the result never depends on claim order.
ROLE_PRECEDENCE = ("compliance_officer", "category_manager", "store_associate", "guest")

DEMO_USERS: dict[str, dict[str, str]] = {
    "guest": {"user_id": "u-guest", "role": "guest", "name": "Guest Shopper"},
    "associate": {"user_id": "u-assoc", "role": "store_associate", "name": "Store Associate"},
    "manager": {"user_id": "u-mgr", "role": "category_manager", "name": "Category Manager"},
    "compliance": {"user_id": "u-comp", "role": "compliance_officer", "name": "Compliance Officer"},
}


@dataclass(frozen=True)
class Principal:
    user_id: str
    role: str
    name: str = ""

    @property
    def allowed_classifications(self) -> set[str]:
        return ROLE_CLEARANCE.get(self.role, {"public"})


class AuthError(Exception):
    """The request is not authenticated. Maps to 401."""


class AuthDisabledError(AuthError):
    """Raised when demo auth is off and no real IdP is configured."""


class UnknownRoleError(Exception):
    """The token is valid but carries no platform role. Maps to 403, never to guest."""


class AuthUnavailableError(Exception):
    """The signing keys cannot be fetched, so the token cannot be judged. Maps to 503."""


def can_access(principal: Principal, classification: str, allowed_roles: Iterable[str] | None = None) -> bool:
    if classification not in principal.allowed_classifications:
        return False
    if allowed_roles:
        return principal.role in set(allowed_roles) or "all" in set(allowed_roles)
    return True


def _fetch_jwks(url: str) -> dict[str, Any]:
    response = httpx.get(url, timeout=5.0)
    response.raise_for_status()
    return response.json()


class JwksCache:
    """Signing keys by `kid`, refreshed on a schedule and on an unknown `kid`.

    An unknown `kid` is attacker-controlled input, so refreshes triggered by one are rate limited.
    """

    def __init__(
        self,
        url: str,
        *,
        fetch: Callable[[str], dict[str, Any]] = _fetch_jwks,
        max_age: float = 300.0,
        min_refresh_interval: float = 30.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._url = url
        self._fetch = fetch
        self._max_age = max_age
        self._min_refresh_interval = min_refresh_interval
        self._clock = clock
        self._keys: dict[str, Any] = {}
        self._fetched_at: float | None = None
        self._lock = threading.Lock()

    def _refresh_locked(self) -> None:
        self._fetched_at = self._clock()
        key_set = jwt.PyJWKSet.from_dict(self._fetch(self._url))
        # Keycloak also publishes an encryption key, which must never verify a signature.
        self._keys = {k.key_id: k for k in key_set.keys if k.key_id and k.public_key_use != "enc"}

    def key_for(self, kid: str) -> Any:
        with self._lock:
            now = self._clock()
            age = None if self._fetched_at is None else now - self._fetched_at
            stale = age is None or age >= self._max_age
            miss = kid not in self._keys and (age is None or age >= self._min_refresh_interval)
            if stale or miss:
                try:
                    self._refresh_locked()
                except (httpx.HTTPError, ValueError, jwt.PyJWTError) as exc:
                    # Keys already held stay usable through a short IdP outage.
                    if kid not in self._keys:
                        raise AuthUnavailableError("cannot fetch signing keys") from exc
            key = self._keys.get(kid)
        if key is None:
            raise AuthError("unknown signing key")
        return key.key


class OidcVerifier:
    """Validates signature, pinned algorithms, issuer, audience and expiry of an access token."""

    def __init__(
        self,
        *,
        issuer: str,
        audience: str,
        algorithms: Iterable[str],
        jwks: JwksCache,
        leeway_seconds: float = 5.0,
    ) -> None:
        self.issuer = issuer
        self.audience = audience
        self.algorithms = list(algorithms)
        self.jwks = jwks
        self.leeway_seconds = leeway_seconds

    def verify(self, token: str) -> dict[str, Any]:
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError as exc:
            raise AuthError("malformed token") from exc
        # Checked before the key lookup, so a forged header cannot trigger a JWKS fetch.
        if header.get("alg") not in self.algorithms:
            raise AuthError("algorithm not allowed")
        kid = header.get("kid")
        if not isinstance(kid, str) or not kid:
            raise AuthError("token has no key id")
        key = self.jwks.key_for(kid)
        try:
            return jwt.decode(
                token,
                key=key,
                algorithms=self.algorithms,
                audience=self.audience,
                issuer=self.issuer,
                leeway=self.leeway_seconds,
                options={"require": ["exp", "iat", "iss", "aud", "sub"]},
            )
        except jwt.PyJWTError as exc:
            raise AuthError(f"invalid token: {type(exc).__name__}") from exc


def principal_from_claims(claims: dict[str, Any]) -> Principal:
    """Map verified claims to a Principal. `sub` becomes `user_id`, which keeps dialog threads per user."""
    realm_access = claims.get("realm_access")
    held = realm_access.get("roles") if isinstance(realm_access, dict) else None
    held = set(held) if isinstance(held, list) else set()
    role = next((r for r in ROLE_PRECEDENCE if r in held), None)
    if role is None:
        raise UnknownRoleError("token carries no platform role")
    name = claims.get("preferred_username") or claims.get("name") or ""
    return Principal(user_id=str(claims["sub"]), role=role, name=str(name))


def _bearer_value(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, value = authorization.partition(" ")
    if scheme.lower() != "bearer" or not value.strip():
        raise AuthError("expected a bearer token")
    return value.strip()


def _demo_principal(authorization: str | None) -> Principal:
    """Demo mode: no header is the anonymous guest, a role key picks that demo user, anything else is rejected."""
    value = _bearer_value(authorization) if authorization and " " in authorization else authorization
    if not value:
        return Principal(**DEMO_USERS["guest"])
    key = value.strip().lower()
    if key in DEMO_USERS:
        return Principal(**DEMO_USERS[key])
    for user in DEMO_USERS.values():
        if user["role"] == key:
            return Principal(**user)
    raise AuthError("unknown demo token")


def resolve_principal(
    authorization: str | None,
    *,
    demo_auth_enabled: bool = True,
    verifier: OidcVerifier | None = None,
) -> Principal:
    """Resolve the request's Principal, or raise. There is no fallback from one mode to the other."""
    if verifier is not None:
        if demo_auth_enabled:
            raise AuthDisabledError("demo auth and OIDC cannot be enabled together")
        token = _bearer_value(authorization)
        if token is None:
            raise AuthError("missing bearer token")
        return principal_from_claims(verifier.verify(token))
    if not demo_auth_enabled:
        raise AuthDisabledError("demo auth disabled; real IdP not configured")
    return _demo_principal(authorization)
