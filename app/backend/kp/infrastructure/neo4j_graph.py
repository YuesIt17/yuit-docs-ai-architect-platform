"""Neo4j adapter: Document/Entity graph with HAS_ALLERGEN / GOVERNS / ABOUT + ACL-aware resolve."""

from __future__ import annotations

import logging
from typing import Any

from kp.config import Settings
from kp.domain.nodes import DocumentNode, EntityNode, LabelAssetNode
from kp.security.rbac import Principal, can_access

logger = logging.getLogger("kp.neo4j")


class Neo4jGraphRepository:
    """Thin Neo4j client used when STORE_BACKEND=live."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._driver = None
        try:
            from neo4j import GraphDatabase

            self._driver = GraphDatabase.driver(
                settings.neo4j_uri,
                auth=(settings.neo4j_user, settings.neo4j_password),
            )
            self._driver.verify_connectivity()
        except Exception as exc:
            logger.warning("Neo4j unavailable: %s", exc)
            self._driver = None

    @property
    def available(self) -> bool:
        return self._driver is not None

    def close(self) -> None:
        if self._driver:
            self._driver.close()
            self._driver = None

    def upsert_document(self, doc: DocumentNode) -> None:
        if not self._driver:
            return
        with self._driver.session() as session:
            session.run(
                """
                MERGE (d:Document {doc_id: $doc_id})
                SET d.title=$title, d.corpus=$corpus, d.classification=$classification,
                    d.allowed_roles=$allowed_roles, d.text=$text,
                    d.index_version=$index_version
                """,
                doc_id=doc.doc_id,
                title=doc.title,
                corpus=doc.corpus,
                classification=doc.classification,
                allowed_roles=doc.allowed_roles,
                text=doc.text,
                index_version=self.settings.index_version,
            )

    def upsert_entity(self, entity: EntityNode, documents: dict[str, DocumentNode] | None = None) -> None:
        if not self._driver:
            return
        docs = documents or {}
        with self._driver.session() as session:
            session.run(
                "MERGE (e:Entity {entity_id:$id}) SET e.name=$name, e.type=$type",
                id=entity.entity_id,
                name=entity.name,
                type=entity.entity_type,
            )
            for did in entity.linked_doc_ids:
                doc = docs.get(did)
                session.run(
                    """
                    MATCH (e:Entity {entity_id:$eid}), (d:Document {doc_id:$did})
                    MERGE (e)-[:ABOUT]->(d)
                    """,
                    eid=entity.entity_id,
                    did=did,
                )
                if entity.entity_type == "allergen" and doc is not None:
                    if doc.corpus == "policy":
                        session.run(
                            """
                            MATCH (e:Entity {entity_id:$eid}), (d:Document {doc_id:$did})
                            MERGE (d)-[:GOVERNS]->(e)
                            """,
                            eid=entity.entity_id,
                            did=did,
                        )
                    else:
                        session.run(
                            """
                            MATCH (e:Entity {entity_id:$eid}), (d:Document {doc_id:$did})
                            MERGE (d)-[:HAS_ALLERGEN]->(e)
                            """,
                            eid=entity.entity_id,
                            did=did,
                        )

    def upsert_label(self, asset: LabelAssetNode) -> None:
        if not self._driver:
            return
        with self._driver.session() as session:
            session.run(
                """
                MERGE (l:LabelAsset {asset_id:$id})
                SET l.source_format=$fmt, l.s3_uri_raw=$raw, l.s3_uri_recognized=$rec,
                    l.classification=$classification
                """,
                id=asset.asset_id,
                fmt=asset.source_format,
                raw=asset.s3_uri_raw,
                rec=asset.s3_uri_recognized,
                classification=asset.classification,
            )

    def graph_resolve_doc_ids(
        self,
        query: str,
        principal: Principal | None = None,
        *,
        max_candidates: int = 24,
    ) -> list[str]:
        """Resolve docs via entity name match + one-hop HAS_ALLERGEN/GOVERNS.

        ACL: filter document nodes by clearance before returning ids.
        """
        if not self._driver:
            return []
        q = query.lower()
        with self._driver.session() as session:
            rows = session.run(
                """
                MATCH (e:Entity)
                RETURN e.name AS name, e.entity_id AS id, e.type AS type
                LIMIT 500
                """
            )
            hits: list[str] = []
            seen: set[str] = set()
            for row in rows:
                name = (row["name"] or "").lower()
                if not name:
                    continue
                if not (name in q or any(tok in q for tok in name.split() if len(tok) > 3)):
                    continue
                linked = session.run(
                    """
                    MATCH (e:Entity {entity_id:$id})
                    OPTIONAL MATCH (e)-[:ABOUT]->(d1:Document)
                    OPTIONAL MATCH (d2:Document)-[:HAS_ALLERGEN|GOVERNS]->(e)
                    WITH collect(DISTINCT d1) + collect(DISTINCT d2) AS docs
                    UNWIND docs AS d
                    WITH d WHERE d IS NOT NULL
                    RETURN d.doc_id AS doc_id, d.classification AS classification,
                           d.allowed_roles AS allowed_roles
                    LIMIT $limit
                    """,
                    id=row["id"],
                    limit=max_candidates,
                )
                for r in linked:
                    doc_id = r["doc_id"]
                    if not doc_id or doc_id in seen:
                        continue
                    if principal is not None:
                        roles = r["allowed_roles"] or []
                        if not can_access(principal, r["classification"] or "public", roles):
                            continue
                    seen.add(doc_id)
                    hits.append(doc_id)
                    if len(hits) >= max_candidates:
                        return hits
            return hits

    def push_all(
        self,
        documents: dict[str, DocumentNode],
        entities: dict[str, EntityNode],
        labels: dict[str, LabelAssetNode],
        *,
        clear: bool = False,
    ) -> dict[str, Any]:
        """Bulk sync used by pipelines/sync_neo4j."""
        if not self._driver:
            raise RuntimeError("Neo4j driver not available")
        with self._driver.session() as session:
            if clear:
                session.run("MATCH (n) DETACH DELETE n")
        for doc in documents.values():
            self.upsert_document(doc)
        for ent in entities.values():
            self.upsert_entity(ent, documents)
        for asset in labels.values():
            self.upsert_label(asset)
        return {
            "documents": len(documents),
            "entities": len(entities),
            "labels": len(labels),
        }
