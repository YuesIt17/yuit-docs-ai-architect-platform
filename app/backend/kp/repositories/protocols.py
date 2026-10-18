"""Store contracts used by the agent and application layer."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from kp.domain.nodes import DocumentNode, LabelAssetNode, RetrievedChunk
from kp.security.rbac import Principal


@runtime_checkable
class KnowledgeStoreProtocol(Protocol):
    """Facade for GraphRAG indexing, retrieval, jobs, audit, and outbox."""

    documents: dict
    chunks: dict
    entities: dict
    labels: dict
    outbox: list
    jobs: dict
    audit: list

    def upsert_document(self, doc: DocumentNode, chunk_texts: list[str] | None = None) -> None: ...

    def upsert_entity(self, name: str, entity_type: str, doc_ids: list[str]) -> str: ...

    def link_topic(self, topic: str, doc_id: str) -> None: ...

    def graph_resolve_doc_ids(self, query: str) -> list[str]: ...

    def hybrid_retrieve(self, query: str, principal: Principal, top_k: int = 5) -> list[RetrievedChunk]: ...

    def add_label_asset(self, asset: LabelAssetNode) -> None: ...

    def push_outbox(self, event_type: str, payload: dict[str, Any]) -> None: ...

    def create_job(self, job_type: str, request: dict[str, Any]) -> str: ...

    def complete_job(self, job_id: str, result: dict[str, Any]) -> None: ...

    def graph_stats(self) -> dict[str, int]: ...
