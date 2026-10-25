"""GraphRAG domain nodes shared by memory and live stores."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DocumentNode:
    doc_id: str
    title: str
    corpus: str  # product | policy | regulatory
    classification: str
    allowed_roles: list[str]
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ChunkNode:
    chunk_id: str
    doc_id: str
    text: str
    modality: str = "text"
    embedding: list[float] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class EntityNode:
    entity_id: str
    name: str
    entity_type: str
    linked_doc_ids: list[str] = field(default_factory=list)


@dataclass
class LabelAssetNode:
    asset_id: str
    source_format: str
    page_count: int
    classification: str
    s3_uri_raw: str | None
    s3_uri_recognized: str | None
    s3_uri_normalized: str | None
    etag: str | None
    extract: dict[str, Any] = field(default_factory=dict)
    # Demo uploads use a fixed classification; allowed_roles mirrors product docs.
    allowed_roles: list[str] = field(
        default_factory=lambda: ["store_associate", "category_manager", "compliance_officer"]
    )
    original_filename: str | None = None


@dataclass
class RetrievedChunk:
    chunk: ChunkNode
    document: DocumentNode
    score: float
    via: str  # graph | vector | hybrid
