"""Reindex vectors (and optionally wipe Qdrant). Destructive — requires --yes."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from kp.config import get_settings
from kp.deps import get_container
from kp.infrastructure.qdrant_vectors import QdrantVectorRepository
from pipelines.seed_all import seed_store


def main() -> None:
    parser = argparse.ArgumentParser(description="Reindex Knowledge Platform chunks")
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Confirm destructive wipe of the Qdrant collection before rebuild",
    )
    parser.add_argument(
        "--seed",
        action="store_true",
        help="Re-seed documents from datasets/seed before sync",
    )
    args = parser.parse_args()
    settings = get_settings()
    print(
        f"INDEX_VERSION={settings.index_version} "
        f"EMBEDDING_PROVIDER={settings.embedding_provider} "
        f"MODEL={settings.embedding_model} DIM={settings.embedding_dim}"
    )
    if not args.yes:
        raise SystemExit(
            "Refusing to wipe/rebuild without --yes. "
            "This deletes existing Qdrant points for the collection."
        )
    c = get_container()
    if args.seed:
        stats = seed_store(c.store)
        print(f"Seeded: {stats}")
    repo = QdrantVectorRepository(settings)
    if not repo.available:
        raise SystemExit("Qdrant unavailable — cannot reindex live vectors")
    result = repo.replace_all(c.store.chunks, c.store.documents)
    print(f"Reindex complete: {result}")


if __name__ == "__main__":
    main()
