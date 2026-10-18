"""Chat use-case: semantic cache → KnowledgeAgent → audit."""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import AsyncIterator
from typing import Any

from kp.application.audit import record_request_audit
from kp.config import Settings
from kp.deps import AppContainer
from kp.domain.schemas import ChatRequest, ChatResponse, Citation
from kp.infrastructure.cache import CacheEntry
from kp.observability import metrics
from kp.security.rbac import Principal


class ChatService:
    """Orchestrates RAG chat with optional SSE streaming."""

    def __init__(self, container: AppContainer, settings: Settings):
        self.c = container
        self.settings = settings

    async def handle(self, body: ChatRequest, principal: Principal) -> ChatResponse | Any:
        """Run a chat turn; returns ChatResponse or a StreamingResponse payload factory.

        Args:
            body: Chat request (message, session, stream flag).
            principal: Caller role used for ACL and cache keying.

        Returns:
            Either a ChatResponse, or a tuple ("stream", async generator) for SSE.
        """
        started = time.perf_counter()
        request_id = str(uuid.uuid4())
        session_id = body.session_id or str(uuid.uuid4())

        cached = self.c.cache.get(body.message, principal.role, self.settings.index_version)
        if cached:
            metrics.CACHE_HIT_RATE.set(self.c.cache.hit_rate)
            metrics.REQUESTS.labels(endpoint="chat", status="cache").inc()
            return ChatResponse(
                answer=cached.answer,
                citations=[Citation(**x) for x in cached.citations],
                session_id=session_id,
                request_id=request_id,
                acl_decision="allow_cache",
                model_uri="cache://semantic",
                index_version=self.settings.index_version,
            )

        if body.stream:
            metrics.REQUESTS.labels(endpoint="chat", status="stream").inc()
            return ("stream", self._event_stream(body, principal, request_id, session_id, started))

        state = await self.c.agent.arun(
            {
                "request_id": request_id,
                "message": body.message,
                "modality": "chat",
                "role": principal.role,
                "user_id": principal.user_id,
                "errors": [],
            }
        )
        record_request_audit(self.c, self.settings, request_id, principal, state, started, "chat")
        citations = [Citation(**x) for x in state.get("citations") or []]
        if state.get("acl_decision") == "allow":
            self.c.cache.put(
                body.message,
                principal.role,
                CacheEntry(
                    answer=state.get("answer", ""),
                    citations=state.get("citations") or [],
                    index_version=self.settings.index_version,
                ),
            )
        metrics.CACHE_HIT_RATE.set(self.c.cache.hit_rate)
        metrics.REQUESTS.labels(endpoint="chat", status=state.get("acl_decision", "allow")).inc()
        cfg = self.c.llm.get_config()
        return ChatResponse(
            answer=state.get("answer", ""),
            citations=citations,
            session_id=session_id,
            request_id=request_id,
            degraded=state.get("degraded", False),
            acl_decision=state.get("acl_decision", "allow"),
            model_uri=state.get("model_uri") or cfg.model_uri,
            llm_provider=cfg.provider,
            index_version=self.settings.index_version,
        )

    async def _event_stream(
        self,
        body: ChatRequest,
        principal: Principal,
        request_id: str,
        session_id: str,
        started: float,
    ) -> AsyncIterator[str]:
        state = await self.c.agent.arun(
            {
                "request_id": request_id,
                "message": body.message,
                "modality": "chat",
                "role": principal.role,
                "user_id": principal.user_id,
                "errors": [],
            }
        )
        cfg = self.c.llm.get_config()
        yield (
            "event: meta\ndata: "
            + json.dumps(
                {
                    "request_id": request_id,
                    "session_id": session_id,
                    "model_uri": state.get("model_uri") or cfg.model_uri,
                    "llm_provider": cfg.provider,
                }
            )
            + "\n\n"
        )
        payload = {
            "answer": state.get("answer", ""),
            "citations": state.get("citations") or [],
            "degraded": state.get("degraded", False),
            "acl_decision": state.get("acl_decision", "allow"),
            "model_uri": state.get("model_uri") or cfg.model_uri,
            "llm_provider": cfg.provider,
        }
        yield f"event: final\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
        record_request_audit(self.c, self.settings, request_id, principal, state, started, "chat")
