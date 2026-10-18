"""Knowledge facade: memory always, Neo4j/Qdrant write-through + retrieve when live."""

from __future__ import annotations

import logging
import re
from typing import Any

from kp.domain.nodes import DocumentNode, LabelAssetNode, RetrievedChunk
from kp.infrastructure.embeddings import EmbeddingService
from kp.infrastructure.neo4j_graph import Neo4jGraphRepository
from kp.infrastructure.qdrant_vectors import QdrantVectorRepository
from kp.repositories.memory_store import MemoryKnowledgeStore
from kp.security.rbac import Principal

logger = logging.getLogger("kp.store")

_MIN_VECTOR_SCORE = 0.18
_STOP = {
    "что",
    "как",
    "про",
    "для",
    "это",
    "или",
    "the",
    "and",
    "for",
    "about",
    "with",
    "know",
    "знаешь",
    "расскажи",
    "какие",
}


def _tokens(text: str) -> set[str]:
    return {
        t
        for t in re.findall(r"[\wа-яё]+", text.lower(), flags=re.IGNORECASE)
        if len(t) > 2 and t not in _STOP
    }


def _lexical_hits(query: str, text: str) -> int:
    q = _tokens(query)
    if not q:
        return 0
    return len(q & _tokens(text))


class HybridKnowledgeStore:
    """
    Unified GraphRAG store.

    Always keeps an in-memory index (jobs/audit/outbox + fast local path).
    When Neo4j and Qdrant are available, upserts write-through and retrieve
    prefers the live backends with memory fallback.
    """

    def __init__(
        self,
        memory: MemoryKnowledgeStore,
        neo4j: Neo4jGraphRepository | None = None,
        qdrant: QdrantVectorRepository | None = None,
        *,
        use_live: bool = False,
    ):
        self._memory = memory
        self._neo4j = neo4j
        self._qdrant = qdrant
        self._use_live = bool(
            use_live and neo4j is not None and neo4j.available and qdrant is not None and qdrant.available
        )

    @property
    def documents(self):
        return self._memory.documents

    @property
    def chunks(self):
        return self._memory.chunks

    @property
    def entities(self):
        return self._memory.entities

    @property
    def labels(self):
        return self._memory.labels

    @property
    def outbox(self):
        return self._memory.outbox

    @property
    def jobs(self):
        return self._memory.jobs

    @property
    def audit(self):
        return self._memory.audit

    @property
    def embeddings(self) -> EmbeddingService:
        return self._memory.embeddings

    @property
    def live_enabled(self) -> bool:
        return self._use_live

    def upsert_document(self, doc: DocumentNode, chunk_texts: list[str] | None = None) -> None:
        self._memory.upsert_document(doc, chunk_texts)
        if not self._use_live:
            return
        try:
            assert self._neo4j and self._qdrant
            self._neo4j.upsert_document(doc)
            for chunk in self._memory.chunks.values():
                if chunk.doc_id == doc.doc_id:
                    self._qdrant.upsert_chunk(chunk, doc)
        except Exception as exc:
            logger.warning("live upsert_document failed: %s", exc)

    def upsert_entity(self, name: str, entity_type: str, doc_ids: list[str]) -> str:
        eid = self._memory.upsert_entity(name, entity_type, doc_ids)
        if self._use_live and self._neo4j:
            try:
                ent = self._memory.entities[eid]
                self._neo4j.upsert_entity(ent)
            except Exception as exc:
                logger.warning("live upsert_entity failed: %s", exc)
        return eid

    def link_topic(self, topic: str, doc_id: str) -> None:
        self._memory.link_topic(topic, doc_id)

    def graph_resolve_doc_ids(self, query: str) -> list[str]:
        if self._use_live and self._neo4j:
            try:
                ids = self._neo4j.graph_resolve_doc_ids(query)
                if ids:
                    return ids
            except Exception as exc:
                logger.warning("live graph_resolve failed: %s", exc)
        return self._memory.graph_resolve_doc_ids(query)

    def hybrid_retrieve(self, query: str, principal: Principal, top_k: int = 5) -> list[RetrievedChunk]:
        if self._use_live and self._qdrant:
            try:
                return self._live_hybrid_retrieve(query, principal, top_k)
            except Exception as exc:
                logger.warning("live hybrid_retrieve failed, memory fallback: %s", exc)
        return self._memory.hybrid_retrieve(query, principal, top_k)

    def _live_hybrid_retrieve(
        self, query: str, principal: Principal, top_k: int
    ) -> list[RetrievedChunk]:
        assert self._qdrant is not None
        qvec = self._memory.embeddings.embed(query)
        graph_ids = self.graph_resolve_doc_ids(query)
        if graph_ids:
            graph_hits = self._qdrant.search(qvec, principal, top_k=top_k, doc_allowlist=graph_ids)
            for h in graph_hits:
                h.via = "hybrid"
            if graph_hits:
                vec_hits = self._qdrant.search(qvec, principal, top_k=top_k)
                merged: dict[str, RetrievedChunk] = {h.chunk.chunk_id: h for h in graph_hits}
                for h in vec_hits:
                    if h.chunk.chunk_id not in merged:
                        merged[h.chunk.chunk_id] = h
                    else:
                        merged[h.chunk.chunk_id].score = max(merged[h.chunk.chunk_id].score, h.score) + 0.05
                hits = sorted(merged.values(), key=lambda x: x.score, reverse=True)[: max(top_k * 3, 15)]
                return self._rerank_and_filter(query, hits, top_k)
        hits = self._qdrant.search(qvec, principal, top_k=max(top_k * 3, 15))
        return self._rerank_and_filter(query, hits, top_k)

    def _rerank_and_filter(self, query: str, hits: list[RetrievedChunk], top_k: int) -> list[RetrievedChunk]:
        ranked: list[RetrievedChunk] = []
        for h in hits:
            lex = _lexical_hits(query, f"{h.document.title} {h.chunk.text}")
            if lex:
                h.score = h.score + 0.35 * min(lex, 3)
                h.via = "hybrid" if h.via == "vector" else h.via
            ranked.append(h)
        ranked.sort(key=lambda x: x.score, reverse=True)
        kept = [
            h
            for h in ranked
            if _lexical_hits(query, f"{h.document.title} {h.chunk.text}") > 0 or h.score >= _MIN_VECTOR_SCORE
        ]
        lexical = [h for h in kept if _lexical_hits(query, f"{h.document.title} {h.chunk.text}") > 0]
        if lexical:
            return lexical[:top_k]
        return kept[:top_k]

    def add_label_asset(self, asset: LabelAssetNode) -> None:
        self._memory.add_label_asset(asset)
        if self._use_live and self._neo4j:
            try:
                self._neo4j.upsert_label(asset)
            except Exception as exc:
                logger.warning("live add_label_asset failed: %s", exc)

    def push_outbox(self, event_type: str, payload: dict[str, Any]) -> None:
        self._memory.push_outbox(event_type, payload)

    def create_job(self, job_type: str, request: dict[str, Any]) -> str:
        return self._memory.create_job(job_type, request)

    def complete_job(self, job_id: str, result: dict[str, Any]) -> None:
        self._memory.complete_job(job_id, result)

    def graph_stats(self) -> dict[str, int]:
        stats = self._memory.graph_stats()
        stats["live"] = 1 if self._use_live else 0
        return stats


# Prefer this name in DI / agent typing.
KnowledgeStore = HybridKnowledgeStore
