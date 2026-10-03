"""RBAC for RetailPartnerX Knowledge Platform."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

ROLE_CLEARANCE: dict[str, set[str]] = {
    "guest": {"public"},
    "store_associate": {"public", "internal"},
    "category_manager": {"public", "internal"},
    "compliance_officer": {"public", "internal", "secret"},
}

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


def can_access(principal: Principal, classification: str, allowed_roles: Iterable[str] | None = None) -> bool:
    if classification not in principal.allowed_classifications:
        return False
    if allowed_roles:
        return principal.role in set(allowed_roles) or "all" in set(allowed_roles)
    return True


def resolve_principal(token_or_role: str | None) -> Principal:
    """MVP auth: Bearer <demo_key> or raw role name. Replace with real JWT in prod."""
    if not token_or_role:
        return Principal(**DEMO_USERS["guest"])
    key = token_or_role.removeprefix("Bearer ").strip().lower()
    if key in DEMO_USERS:
        return Principal(**DEMO_USERS[key])
    for user in DEMO_USERS.values():
        if user["role"] == key:
            return Principal(**user)
    return Principal(user_id="u-unknown", role="guest", name="Unknown")
