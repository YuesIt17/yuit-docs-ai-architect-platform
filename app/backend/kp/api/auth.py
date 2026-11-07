"""Who is calling, and how the platform authenticates."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from kp.api.deps import principal_dep
from kp.config import Settings, get_settings
from kp.domain.schemas import AuthModeResponse, MeResponse
from kp.security.rbac import Principal

router = APIRouter(prefix="/v1", tags=["auth"])


@router.get("/auth/mode", response_model=AuthModeResponse)
async def auth_mode(settings: Settings = Depends(get_settings)):
    """Public: the UI reads this before login to decide between the role switcher and the login button."""
    return AuthModeResponse(mode="oidc" if settings.oidc_issuer else "demo")


@router.get("/me", response_model=MeResponse)
async def me(principal: Principal = Depends(principal_dep)):
    return MeResponse(
        user_id=principal.user_id,
        role=principal.role,
        name=principal.name,
        allowed_classifications=sorted(principal.allowed_classifications),
    )
