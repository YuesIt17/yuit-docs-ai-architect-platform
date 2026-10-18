"""Chat HTTP routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from kp.api.deps import container_dep, principal_dep
from kp.application.chat import ChatService
from kp.config import Settings, get_settings
from kp.deps import AppContainer
from kp.domain.schemas import ChatRequest, ChatResponse

router = APIRouter(tags=["chat"])


@router.post("/v1/chat", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    principal=Depends(principal_dep),
    c: AppContainer = Depends(container_dep),
    settings: Settings = Depends(get_settings),
):
    result = await ChatService(c, settings).handle(body, principal)
    if isinstance(result, tuple) and result[0] == "stream":
        return StreamingResponse(result[1], media_type="text/event-stream")
    return result
