"""Optional: push in-memory graph into Neo4j for Browser demo."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from kp.config import get_settings
from kp.deps import get_container
from kp.infrastructure.neo4j_graph import Neo4jGraphRepository
from pipelines.seed_all import seed_store


def sync() -> None:
    settings = get_settings()
    c = get_container()
    seed_store(c.store)
    repo = Neo4jGraphRepository(settings)
    if not repo.available:
        raise SystemExit("Neo4j unavailable")
    stats = repo.push_all(c.store.documents, c.store.entities, c.store.labels, clear=True)
    repo.close()
    print("Neo4j sync complete", stats, c.store.graph_stats())


if __name__ == "__main__":
    sync()
