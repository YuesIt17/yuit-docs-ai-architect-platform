"""Optional: upsert chunks into Qdrant with ACL payload."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from kp.config import get_settings
from kp.deps import get_container
from kp.infrastructure.qdrant_vectors import QdrantVectorRepository
from pipelines.seed_all import seed_store


def sync() -> None:
    settings = get_settings()
    c = get_container()
    seed_store(c.store)
    repo = QdrantVectorRepository(settings)
    if not repo.available:
        raise SystemExit("Qdrant unavailable")
    stats = repo.replace_all(c.store.chunks, c.store.documents)
    print(f"Qdrant sync complete: {stats}")


if __name__ == "__main__":
    sync()
