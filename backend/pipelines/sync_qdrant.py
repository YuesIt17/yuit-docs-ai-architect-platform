"""Optional: upsert chunks into Qdrant with ACL payload."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, PointStruct, VectorParams

from app.config import get_settings
from app.deps import get_container
from pipelines.seed_all import seed_store

COLLECTION = "kp_chunks"


def sync() -> None:
    settings = get_settings()
    c = get_container()
    seed_store(c.store)
    client = QdrantClient(url=settings.qdrant_url)
    if COLLECTION in [x.name for x in client.get_collections().collections]:
        client.delete_collection(COLLECTION)
    client.create_collection(
        COLLECTION,
        vectors_config=VectorParams(size=settings.embedding_dim, distance=Distance.COSINE),
    )
    points = []
    for i, chunk in enumerate(c.store.chunks.values()):
        doc = c.store.documents[chunk.doc_id]
        points.append(
            PointStruct(
                id=i,
                vector=chunk.embedding,
                payload={
                    "chunk_id": chunk.chunk_id,
                    "doc_id": chunk.doc_id,
                    "text": chunk.text,
                    "classification": doc.classification,
                    "allowed_roles": doc.allowed_roles,
                    "corpus": doc.corpus,
                    "index_version": settings.index_version,
                },
            )
        )
    if points:
        client.upsert(COLLECTION, points=points)
    print(f"Qdrant sync complete: {len(points)} points")


if __name__ == "__main__":
    sync()
