"""Chat use-case: Input Guard → semantic cache (re-auth) → KnowledgeAgent → audit."""

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
from kp.observability.spans import current_trace_id, span
from kp.security.guardrails import input_guard, output_guard
from kp.security.rbac import Principal, can_access


class ChatService:
    """Orchestrates RAG chat with optional SSE streaming."""

    def __init__(self, container: AppContainer, settings: Settings):
        self.c = container
        self.settings = settings

    def _cache_model_uri(self) -> str:
        return self.c.llm.get_config().model_uri

    def _authorize_cached_sources(self, principal: Principal, entry: CacheEntry) -> bool:
        """Re-check ACL on every cited source against live document metadata.

        Returns False (treat as miss) if any source is missing or inaccessible.
        """
        docs = self.c.store.documents
        doc_ids = list(entry.source_doc_ids) or [
            str(c.get("doc_id")) for c in entry.citations if c.get("doc_id")
        ]
        if not doc_ids and entry.citations:
            return False
        for doc_id in doc_ids:
            doc = docs.get(doc_id)
            if doc is None:
                return False
            if not can_access(principal, doc.classification, doc.allowed_roles):
                return False
        # Refresh citation classifications from live metadata
        for cit in entry.citations:
            doc = docs.get(cit.get("doc_id"))
            if doc is None:
                return False
            cit["classification"] = doc.classification
            if not can_access(principal, doc.classification, doc.allowed_roles):
                return False
        return True

    def _lookup_cache(self, message: str, principal: Principal) -> CacheEntry | None:
        entry = self.c.cache.get(
            message,
            principal.role,
            self.settings.index_version,
            policy_version=self.settings.policy_version,
            prompt_version=self.settings.prompt_version,
            model_uri=self._cache_model_uri(),
        )
        if not entry:
            return None
        if not self._authorize_cached_sources(principal, entry):
            self.c.cache.misses += 1
            if self.c.cache.hits > 0:
                self.c.cache.hits -= 1
            return None
        # Output guard + PII on cache hit
        classifications = [c.get("classification", "public") for c in entry.citations]
        guarded = output_guard(entry.answer, entry.citations, principal.role, classifications)
        if not guarded.ok:
            return None
        entry.answer = guarded.text
        return entry

    def _maybe_put_cache(
        self,
        message: str,
        principal: Principal,
        state: dict[str, Any],
    ) -> None:
        if state.get("acl_decision") != "allow":
            return
        if state.get("degraded"):
            return
        citations = state.get("citations") or []
        source_ids = [str(c.get("doc_id")) for c in citations if c.get("doc_id")]
        self.c.cache.put(
            message,
            principal.role,
            CacheEntry(
                answer=state.get("answer", ""),
                citations=citations,
                index_version=self.settings.index_version,
                policy_version=self.settings.policy_version,
                prompt_version=self.settings.prompt_version,
                model_uri=self._cache_model_uri(),
                source_doc_ids=source_ids,
            ),
        )

    def _cache_response(
        self,
        *,
        cached: CacheEntry,
        session_id: str,
        request_id: str,
    ) -> ChatResponse:
        cfg = self.c.llm.get_config()
        return ChatResponse(
            answer=cached.answer,
            citations=[Citation(**x) for x in cached.citations],
            session_id=session_id,
            request_id=request_id,
            acl_decision="allow_cache",
            model_uri="cache://semantic",
            llm_provider=cfg.provider,
            index_version=self.settings.index_version,
        )

    async def handle(self, body: ChatRequest, principal: Principal) -> ChatResponse | Any:
        """Run a chat turn; returns ChatResponse or ("stream", async generator) for SSE."""
        started = time.perf_counter()
        request_id = str(uuid.uuid4())
        session_id = body.session_id or str(uuid.uuid4())

        # SEC-01: Input Guard before cache lookup
        guard = input_guard(body.message)
        if not guard.ok:
            metrics.REQUESTS.labels(endpoint="chat", status="guard_deny").inc()
            denied = {
                "answer": "Запрос отклонён input guard (подозрение на prompt injection).",
                "citations": [],
                "acl_decision": "deny_input",
                "degraded": False,
                "model_uri": self._cache_model_uri(),
                "tokens_in": 0,
                "tokens_out": 0,
            }
            record_request_audit(self.c, self.settings, request_id, principal, denied, started, "chat")
            if body.stream:
                return ("stream", self._deny_stream(denied, request_id, session_id))
            return ChatResponse(
                answer=denied["answer"],
                citations=[],
                session_id=session_id,
                request_id=request_id,
                acl_decision="deny_input",
                model_uri=denied["model_uri"],
                llm_provider=self.c.llm.get_config().provider,
                index_version=self.settings.index_version,
            )
        message = guard.text

        with span("cache", request_id=request_id, role=principal.role):
            cached = self._lookup_cache(message, principal)
        if cached:
            metrics.CACHE_HIT_RATE.set(self.c.cache.hit_rate)
            metrics.REQUESTS.labels(endpoint="chat", status="cache").inc()
            state = {
                "answer": cached.answer,
                "citations": cached.citations,
                "acl_decision": "allow_cache",
                "degraded": False,
                "model_uri": "cache://semantic",
                # Cache hit: no inference token recount
                "tokens_in": 0,
                "tokens_out": 0,
                "trace_id": current_trace_id(),
            }
            record_request_audit(self.c, self.settings, request_id, principal, state, started, "chat")
            if body.stream:
                return ("stream", self._cache_stream(cached, request_id, session_id))
            return self._cache_response(cached=cached, session_id=session_id, request_id=request_id)

        if body.stream:
            metrics.REQUESTS.labels(endpoint="chat", status="stream").inc()
            return ("stream", self._event_stream(message, principal, request_id, session_id, started))

        state = await self.c.agent.arun(
            {
                "request_id": request_id,
                "message": message,
                "modality": "chat",
                "role": principal.role,
                "user_id": principal.user_id,
                "errors": [],
            }
        )
        # Attach active OTel trace for audit / Loki↔Tempo correlation
        if not state.get("trace_id"):
            state["trace_id"] = current_trace_id()
        record_request_audit(self.c, self.settings, request_id, principal, state, started, "chat")
        citations = [Citation(**x) for x in state.get("citations") or []]
        self._maybe_put_cache(message, principal, state)
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

    async def _deny_stream(
        self, denied: dict[str, Any], request_id: str, session_id: str
    ) -> AsyncIterator[str]:
        cfg = self.c.llm.get_config()
        yield (
            "event: meta\ndata: "
            + json.dumps(
                {
                    "request_id": request_id,
                    "session_id": session_id,
                    "model_uri": denied.get("model_uri"),
                    "llm_provider": cfg.provider,
                }
            )
            + "\n\n"
        )
        payload = {
            "answer": denied["answer"],
            "citations": [],
            "degraded": False,
            "acl_decision": "deny_input",
            "model_uri": denied.get("model_uri"),
            "llm_provider": cfg.provider,
        }
        yield f"event: final\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"

    async def _cache_stream(
        self, cached: CacheEntry, request_id: str, session_id: str
    ) -> AsyncIterator[str]:
        cfg = self.c.llm.get_config()
        yield (
            "event: meta\ndata: "
            + json.dumps(
                {
                    "request_id": request_id,
                    "session_id": session_id,
                    "model_uri": "cache://semantic",
                    "llm_provider": cfg.provider,
                    "cache_hit": True,
                }
            )
            + "\n\n"
        )
        payload = {
            "answer": cached.answer,
            "citations": cached.citations,
            "degraded": False,
            "acl_decision": "allow_cache",
            "model_uri": "cache://semantic",
            "llm_provider": cfg.provider,
        }
        yield f"event: final\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"

    async def _event_stream(
        self,
        message: str,
        principal: Principal,
        request_id: str,
        session_id: str,
        started: float,
    ) -> AsyncIterator[str]:
        state = await self.c.agent.arun(
            {
                "request_id": request_id,
                "message": message,
                "modality": "chat",
                "role": principal.role,
                "user_id": principal.user_id,
                "errors": [],
            }
        )
        self._maybe_put_cache(message, principal, state)
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
        if not state.get("trace_id"):
            state["trace_id"] = current_trace_id()
        record_request_audit(self.c, self.settings, request_id, principal, state, started, "chat")
