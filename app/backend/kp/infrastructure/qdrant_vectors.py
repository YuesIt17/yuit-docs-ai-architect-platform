"""Qdrant adapter for chunk upsert and ACL-aware vector search on the live path."""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from kp.config import Settings
from kp.domain.nodes import ChunkNode, DocumentNode, RetrievedChunk
from kp.security.rbac import Principal, can_access

logger = logging.getLogger("kp.qdrant")

COLLECTION = "kp_chunks"


def _point_id(chunk_id: str) -> int:
    """Stable positive int id for Qdrant (avoids uuid dependency)."""
    digest = hashlib.sha256(chunk_id.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % (2**63 - 1)


class QdrantVectorRepository:
    """Thin Qdrant client used when STORE_BACKEND=live."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._client = None
        try:
            from qdrant_client import QdrantClient

            self._client = QdrantClient(url=settings.qdrant_url)
            self._ensure_collection()
        except Exception as exc:
            logger.warning("Qdrant unavailable: %s", exc)
            self._client = None

    @property
    def available(self) -> bool:
        return self._client is not None

    def _ensure_collection(self) -> None:
        from qdrant_client.http.models import Distance, VectorParams

        assert self._client is not None
        names = [c.name for c in self._client.get_collections().collections]
        if COLLECTION not in names:
            self._client.create_collection(
                COLLECTION,
                vectors_config=VectorParams(size=self.settings.embedding_dim, distance=Distance.COSINE),
            )

    def upsert_chunk(self, chunk: ChunkNode, doc: DocumentNode) -> None:
        if not self._client or not chunk.embedding:
            return
        from qdrant_client.http.models import PointStruct

        self._client.upsert(
            COLLECTION,
            points=[
                PointStruct(
                    id=_point_id(chunk.chunk_id),
                    vector=chunk.embedding,
                    payload={
                        "chunk_id": chunk.chunk_id,
                        "doc_id": chunk.doc_id,
                        "text": chunk.text,
                        "title": doc.title,
                        "classification": doc.classification,
                        "allowed_roles": doc.allowed_roles,
                        "corpus": doc.corpus,
                        "index_version": self.settings.index_version,
                    },
                )
            ],
        )

    def upsert_chunks(self, chunks: list[ChunkNode], documents: dict[str, DocumentNode]) -> int:
        count = 0
        for chunk in chunks:
            doc = documents.get(chunk.doc_id)
            if not doc:
                continue
            self.upsert_chunk(chunk, doc)
            count += 1
        return count

    def search(
        self,
        query_vector: list[float],
        principal: Principal,
        top_k: int = 5,
        doc_allowlist: list[str] | None = None,
    ) -> list[RetrievedChunk]:
        if not self._client:
            return []
        results = self._client.search(
            collection_name=COLLECTION,
            query_vector=query_vector,
            limit=max(top_k * 4, 20),
        )
        hits: list[RetrievedChunk] = []
        for point in results:
            payload = point.payload or {}
            doc_id = payload.get("doc_id")
            if doc_allowlist is not None and doc_id not in doc_allowlist:
                continue
            classification = payload.get("classification", "public")
            allowed_roles = payload.get("allowed_roles") or []
            if not can_access(principal, classification, allowed_roles):
                continue
            chunk = ChunkNode(
                chunk_id=payload.get("chunk_id", str(point.id)),
                doc_id=doc_id or "",
                text=payload.get("text", ""),
                embedding=[],
                metadata={"corpus": payload.get("corpus"), "classification": classification},
            )
            doc = DocumentNode(
                doc_id=doc_id or "",
                title=payload.get("title", doc_id or ""),
                corpus=payload.get("corpus", "product"),
                classification=classification,
                allowed_roles=list(allowed_roles),
                text=payload.get("text", ""),
            )
            hits.append(RetrievedChunk(chunk=chunk, document=doc, score=float(point.score or 0), via="vector"))
            if len(hits) >= top_k:
                break
        return hits

    def replace_all(self, chunks: dict[str, ChunkNode], documents: dict[str, DocumentNode]) -> dict[str, Any]:
        """Bulk sync used by pipelines/sync_qdrant."""
        if not self._client:
            raise RuntimeError("Qdrant client not available")
        from qdrant_client.http.models import Distance, PointStruct, VectorParams

        names = [c.name for c in self._client.get_collections().collections]
        if COLLECTION in names:
            self._client.delete_collection(COLLECTION)
        self._client.create_collection(
            COLLECTION,
            vectors_config=VectorParams(size=self.settings.embedding_dim, distance=Distance.COSINE),
        )
        points = []
        for i, chunk in enumerate(chunks.values()):
            doc = documents.get(chunk.doc_id)
            if not doc or not chunk.embedding:
                continue
            points.append(
                PointStruct(
                    id=i,
                    vector=chunk.embedding,
                    payload={
                        "chunk_id": chunk.chunk_id,
                        "doc_id": chunk.doc_id,
                        "text": chunk.text,
                        "title": doc.title,
                        "classification": doc.classification,
                        "allowed_roles": doc.allowed_roles,
                        "corpus": doc.corpus,
                        "index_version": self.settings.index_version,
                    },
                )
            )
        if points:
            self._client.upsert(COLLECTION, points=points)
        return {"points": len(points)}
