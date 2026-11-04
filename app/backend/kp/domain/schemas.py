"""Pydantic request/response models for the HTTP API."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str
    # Send the same id to continue a dialog; omit it for a stateless request.
    session_id: str | None = Field(default=None, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    stream: bool = True


class Citation(BaseModel):
    doc_id: str
    chunk_id: str
    corpus: str
    classification: str
    snippet: str
    score: float = 0.0


class ChatResponse(BaseModel):
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    session_id: str
    request_id: str
    degraded: bool = False
    acl_decision: str = "allow"
    model_uri: str | None = None
    llm_provider: str | None = None
    index_version: str | None = None


class LabelExtract(BaseModel):
    brand: str | None = None
    barcode: str | None = None
    net_weight: str | None = None
    ingredients: str | None = None
    allergens: list[str] = Field(default_factory=list)
    pages_processed: int = 1
    confidence: float = 0.0
    raw_ocr_text: str = ""


class LabelResponse(BaseModel):
    asset_id: str
    extract: LabelExtract
    warnings: list[str] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    answer: str
    s3_uri_raw: str | None = None
    s3_uri_recognized: str | None = None
    request_id: str
    degraded: bool = False
    model_uri: str | None = None
    llm_provider: str | None = None
    # Honest MVP marker — real OCR is out of scope for this delivery.
    ocr_provider: str = "MOCK"


class IngestEntity(BaseModel):
    name: str
    type: str


class IngestDocument(BaseModel):
    doc_id: str = Field(min_length=1, max_length=128)
    title: str = Field(max_length=500)
    corpus: str = Field(max_length=64)
    classification: Literal["public", "internal", "secret"]
    allowed_roles: list[Literal["guest", "store_associate", "category_manager", "compliance_officer"]]
    text: str = Field(min_length=1, max_length=200_000)
    entities: list[IngestEntity] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)


class IngestRequest(BaseModel):
    documents: list[IngestDocument] = Field(min_length=1, max_length=1000)


class JobCreateRequest(BaseModel):
    job_type: Literal["batch_label", "multi_hop_chat", "ingest_documents"] = "batch_label"
    payload: dict[str, Any] = Field(default_factory=dict)


class JobResponse(BaseModel):
    job_id: str
    status: str
    result: dict[str, Any] | None = None


class PresignResponse(BaseModel):
    asset_id: str
    kind: Literal["raw", "recognized", "normalized"]
    url: str
    expires_seconds: int = 300


class HealthResponse(BaseModel):
    status: str
    store_backend: str
    llm_provider: str
    llm_model: str | None = None
    llm_reachable: bool | None = None
    index_version: str


class LLMConfigUpdate(BaseModel):
    provider: Literal["MOCK", "OLLAMA", "VLLM"]
    base_url: str | None = None
    model: str | None = None


class LLMConfigResponse(BaseModel):
    provider: str
    base_url: str
    model: str
    model_uri: str
    reachable: bool | None = None
    detail: str | None = None
    presets: dict[str, dict[str, str]] = Field(default_factory=dict)
