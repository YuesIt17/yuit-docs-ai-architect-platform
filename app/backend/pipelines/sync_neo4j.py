"""Optional: push in-memory graph into Neo4j for Browser demo."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import get_settings
from app.deps import get_container
from pipelines.seed_all import seed_store


def sync() -> None:
    settings = get_settings()
    c = get_container()
    seed_store(c.store)
    from neo4j import GraphDatabase

    driver = GraphDatabase.driver(settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password))
    with driver.session() as session:
        session.run("MATCH (n) DETACH DELETE n")
        for doc in c.store.documents.values():
            session.run(
                """
                MERGE (d:Document {doc_id: $doc_id})
                SET d.title=$title, d.corpus=$corpus, d.classification=$classification
                """,
                doc_id=doc.doc_id,
                title=doc.title,
                corpus=doc.corpus,
                classification=doc.classification,
            )
        for ent in c.store.entities.values():
            session.run(
                "MERGE (e:Entity {entity_id:$id}) SET e.name=$name, e.type=$type",
                id=ent.entity_id,
                name=ent.name,
                type=ent.entity_type,
            )
            for did in ent.linked_doc_ids:
                session.run(
                    """
                    MATCH (e:Entity {entity_id:$eid}), (d:Document {doc_id:$did})
                    MERGE (e)-[:ABOUT]->(d)
                    """,
                    eid=ent.entity_id,
                    did=did,
                )
        for asset in c.store.labels.values():
            session.run(
                """
                MERGE (l:LabelAsset {asset_id:$id})
                SET l.source_format=$fmt, l.s3_uri_raw=$raw, l.s3_uri_recognized=$rec
                """,
                id=asset.asset_id,
                fmt=asset.source_format,
                raw=asset.s3_uri_raw,
                rec=asset.s3_uri_recognized,
            )
    driver.close()
    print("Neo4j sync complete", c.store.graph_stats())


if __name__ == "__main__":
    sync()
