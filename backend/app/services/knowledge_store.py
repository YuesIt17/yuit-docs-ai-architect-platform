"""In-memory Graph + Vector store with ACL-aware retrieval (GraphRAG MVP)."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from typing import Any

from app.security.rbac import Principal, can_access
from app.services.embeddings import EmbeddingService

# MOCK embeddings are bag-of-hash — always return a top-k. Drop noise via lexical overlap + score floor.
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


@dataclass
class DocumentNode:
    doc_id: str
    title: str
    corpus: str  # product | policy | regulatory
    classification: str
    allowed_roles: list[str]
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ChunkNode:
    chunk_id: str
    doc_id: str
    text: str
    modality: str = "text"
    embedding: list[float] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class EntityNode:
    entity_id: str
    name: str
    entity_type: str
    linked_doc_ids: list[str] = field(default_factory=list)


@dataclass
class LabelAssetNode:
    asset_id: str
    source_format: str
    page_count: int
    classification: str
    s3_uri_raw: str | None
    s3_uri_recognized: str | None
    s3_uri_normalized: str | None
    etag: str | None
    extract: dict[str, Any] = field(default_factory=dict)


@dataclass
class RetrievedChunk:
    chunk: ChunkNode
    document: DocumentNode
    score: float
    via: str  # graph | vector | hybrid


class KnowledgeStore:
    """Unified GraphRAG store. Memory backend for MVP/tests; same API for live adapters."""

    def __init__(self, embeddings: EmbeddingService):
        self.embeddings = embeddings
        self.documents: dict[str, DocumentNode] = {}
        self.chunks: dict[str, ChunkNode] = {}
        self.entities: dict[str, EntityNode] = {}
        self.topics: dict[str, set[str]] = {}  # topic -> doc_ids
        self.edges: list[tuple[str, str, str]] = []  # (src, rel, dst)
        self.labels: dict[str, LabelAssetNode] = {}
        self.outbox: list[dict[str, Any]] = []
        self.jobs: dict[str, dict[str, Any]] = {}
        self.audit: list[dict[str, Any]] = []

    def upsert_document(self, doc: DocumentNode, chunk_texts: list[str] | None = None) -> None:
        self.documents[doc.doc_id] = doc
        texts = chunk_texts or [doc.text]
        for i, text in enumerate(texts):
            cid = f"{doc.doc_id}::c{i}"
            self.chunks[cid] = ChunkNode(
                chunk_id=cid,
                doc_id=doc.doc_id,
                text=text,
                modality="ocr" if doc.metadata.get("modality") == "ocr" else "text",
                embedding=self.embeddings.embed(text),
                metadata={"corpus": doc.corpus, "classification": doc.classification},
            )
            self.edges.append((doc.doc_id, "CONTAINS", cid))

    def upsert_entity(self, name: str, entity_type: str, doc_ids: list[str]) -> str:
        eid = f"ent:{entity_type}:{name.lower().replace(' ', '_')}"
        existing = self.entities.get(eid)
        if existing:
            existing.linked_doc_ids = sorted(set(existing.linked_doc_ids + doc_ids))
        else:
            self.entities[eid] = EntityNode(entity_id=eid, name=name, entity_type=entity_type, linked_doc_ids=doc_ids)
        for did in doc_ids:
            self.edges.append((eid, "ABOUT", did))
            if entity_type == "allergen":
                self.edges.append((did, "HAS_ALLERGEN", eid))
        return eid

    def link_topic(self, topic: str, doc_id: str) -> None:
        self.topics.setdefault(topic.lower(), set()).add(doc_id)
        self.edges.append((doc_id, "ABOUT", f"topic:{topic.lower()}"))

    def graph_resolve_doc_ids(self, query: str) -> list[str]:
        q = query.lower()
        hits: set[str] = set()
        for ent in self.entities.values():
            if ent.name.lower() in q or any(tok in q for tok in ent.name.lower().split() if len(tok) > 3):
                hits.update(ent.linked_doc_ids)
        for topic, doc_ids in self.topics.items():
            if topic in q:
                hits.update(doc_ids)
        return list(hits)

    def vector_search(self, query: str, principal: Principal, top_k: int = 5, doc_allowlist: list[str] | None = None) -> list[RetrievedChunk]:
        qvec = self.embeddings.embed(query)
        scored: list[RetrievedChunk] = []
        for chunk in self.chunks.values():
            doc = self.documents.get(chunk.doc_id)
            if not doc:
                continue
            if doc_allowlist is not None and doc.doc_id not in doc_allowlist:
                continue
            if not can_access(principal, doc.classification, doc.allowed_roles):
                continue
            score = EmbeddingService.cosine(qvec, chunk.embedding)
            scored.append(RetrievedChunk(chunk=chunk, document=doc, score=score, via="vector"))
        scored.sort(key=lambda x: x.score, reverse=True)
        return scored[:top_k]

    def hybrid_retrieve(self, query: str, principal: Principal, top_k: int = 5) -> list[RetrievedChunk]:
        graph_ids = self.graph_resolve_doc_ids(query)
        if graph_ids:
            graph_hits = self.vector_search(query, principal, top_k=top_k, doc_allowlist=graph_ids)
            for h in graph_hits:
                h.via = "hybrid"
            if graph_hits:
                # merge with global vector for recall
                vec_hits = self.vector_search(query, principal, top_k=top_k)
                merged: dict[str, RetrievedChunk] = {h.chunk.chunk_id: h for h in graph_hits}
                for h in vec_hits:
                    if h.chunk.chunk_id not in merged:
                        merged[h.chunk.chunk_id] = h
                    else:
                        merged[h.chunk.chunk_id].score = max(merged[h.chunk.chunk_id].score, h.score) + 0.05
                hits = sorted(merged.values(), key=lambda x: x.score, reverse=True)[: max(top_k * 3, 15)]
                return self._rerank_and_filter(query, hits, top_k)
        hits = self.vector_search(query, principal, top_k=max(top_k * 3, 15))
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
        kept = [h for h in ranked if _lexical_hits(query, f"{h.document.title} {h.chunk.text}") > 0 or h.score >= _MIN_VECTOR_SCORE]
        # Prefer lexical matches when present — avoids dumping unrelated policies into tiny LLMs
        lexical = [h for h in kept if _lexical_hits(query, f"{h.document.title} {h.chunk.text}") > 0]
        if lexical:
            return lexical[:top_k]
        return kept[:top_k]

    def add_label_asset(self, asset: LabelAssetNode) -> None:
        self.labels[asset.asset_id] = asset

    def push_outbox(self, event_type: str, payload: dict[str, Any]) -> None:
        self.outbox.append({"event_type": event_type, "payload": payload})

    def create_job(self, job_type: str, request: dict[str, Any]) -> str:
        jid = str(uuid.uuid4())
        self.jobs[jid] = {"job_id": jid, "job_type": job_type, "status": "queued", "request": request, "result": None}
        return jid

    def complete_job(self, job_id: str, result: dict[str, Any]) -> None:
        if job_id in self.jobs:
            self.jobs[job_id]["status"] = "completed"
            self.jobs[job_id]["result"] = result

    def graph_stats(self) -> dict[str, int]:
        return {
            "documents": len(self.documents),
            "chunks": len(self.chunks),
            "entities": len(self.entities),
            "edges": len(self.edges),
            "labels": len(self.labels),
        }
