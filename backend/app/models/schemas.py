from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None
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


class JobCreateRequest(BaseModel):
    job_type: Literal["batch_label", "multi_hop_chat"] = "batch_label"
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
    index_version: str
