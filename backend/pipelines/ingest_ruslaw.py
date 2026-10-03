"""Ingest RusLawOD XML acts into KnowledgeStore (subset).

Place XML files under datasets/ruslaw_raw/ and run:
  python -m pipelines.ingest_ruslaw
"""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.deps import get_container
from app.services.knowledge_store import DocumentNode


def parse_act(path: Path) -> DocumentNode | None:
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError:
        return None
    heading = root.findtext(".//headingIPS") or path.stem
    body = root.findtext(".//textIPS") or ""
    status = root.find(".//statusIPS")
    classification = "public"
    if status is not None and (status.get("val") or "").lower().find("секрет") >= 0:
        classification = "secret"
    doc_id = f"reg-{path.stem}"
    return DocumentNode(
        doc_id=doc_id,
        title=heading.strip()[:200],
        corpus="regulatory",
        classification=classification,
        allowed_roles=["guest", "store_associate", "category_manager", "compliance_officer"]
        if classification == "public"
        else ["compliance_officer"],
        text=f"{heading}\n\n{body}"[:8000],
        metadata={"source": "RusLawOD", "path": str(path.name)},
    )


def main() -> None:
    raw = ROOT.parent / "datasets" / "ruslaw_raw"
    c = get_container()
    if not raw.exists():
        print(f"No {raw} — using seed regulatory.json via seed_all instead")
        from pipelines.seed_all import seed_store

        print(seed_store(c.store))
        return
    n = 0
    for path in sorted(raw.glob("*.xml"))[:200]:
        doc = parse_act(path)
        if not doc:
            continue
        c.store.upsert_document(doc)
        c.store.link_topic("regulatory", doc.doc_id)
        n += 1
    print(f"Ingested {n} RusLawOD XML acts", c.store.graph_stats())


if __name__ == "__main__":
    main()
