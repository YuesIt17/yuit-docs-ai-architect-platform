"""Seed Product/Policy/Regulatory KB into KnowledgeStore (+ optional live backends)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Ensure backend root on path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.deps import get_container
from app.services.knowledge_store import DocumentNode


def _datasets_dir() -> Path:
    candidates = [
        ROOT.parent / "datasets" / "seed",
        Path("/datasets/seed"),
        Path("datasets/seed"),
    ]
    for c in candidates:
        if c.exists():
            return c
    raise FileNotFoundError("datasets/seed not found")


def load_json_docs(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def seed_store(store=None) -> dict:
    container = get_container()
    store = store or container.store
    seed_dir = _datasets_dir()
    counts = {"documents": 0, "entities": 0}
    for name in ("products.json", "policies.json", "regulatory.json"):
        for item in load_json_docs(seed_dir / name):
            doc = DocumentNode(
                doc_id=item["doc_id"],
                title=item["title"],
                corpus=item["corpus"],
                classification=item["classification"],
                allowed_roles=item["allowed_roles"],
                text=item["text"],
                metadata={"title": item["title"], "index_version": container.settings.index_version},
            )
            store.upsert_document(doc)
            counts["documents"] += 1
            for ent in item.get("entities") or []:
                store.upsert_entity(ent["name"], ent["type"], [doc.doc_id])
                counts["entities"] += 1
            for topic in item.get("topics") or []:
                store.link_topic(topic, doc.doc_id)
    container._seeded = True
    return {**counts, **store.graph_stats()}


def main() -> None:
    stats = seed_store()
    print(f"Seeded KnowledgeStore: {stats}")


if __name__ == "__main__":
    main()
