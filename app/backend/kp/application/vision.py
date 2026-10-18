"""Vision/label use-case: OCR → object store → GraphRAG index → agent."""

from __future__ import annotations

import time
import uuid

from fastapi import HTTPException

from kp.application.audit import record_request_audit
from kp.config import Settings
from kp.deps import AppContainer
from kp.domain.nodes import DocumentNode, LabelAssetNode
from kp.domain.schemas import Citation, LabelExtract, LabelResponse
from kp.observability import metrics
from kp.security.guardrails import vision_input_guard
from kp.security.rbac import Principal


class VisionServiceApp:
    """Orchestrates multimodal label recognition and policy analysis."""

    def __init__(self, container: AppContainer, settings: Settings):
        self.c = container
        self.settings = settings

    async def recognize_label(
        self,
        *,
        filename: str,
        content_type: str | None,
        data: bytes,
        page_limit: int,
        principal: Principal,
    ) -> LabelResponse:
        """Normalize upload, extract attributes, index OCR, and run label agent.

        Args:
            filename: Original upload name.
            content_type: Declared MIME type.
            data: Raw file bytes.
            page_limit: Max PDF pages to rasterize.
            principal: Caller for ACL on policy retrieval.

        Returns:
            LabelResponse with extract, citations, and agent answer.

        Raises:
            HTTPException: 400 when input guard rejects the upload.
        """
        started = time.perf_counter()
        request_id = str(uuid.uuid4())
        guard = vision_input_guard(filename or "upload.bin", content_type, len(data))
        if not guard.ok:
            metrics.REQUESTS.labels(endpoint="vision", status="guard_deny").inc()
            raise HTTPException(status_code=400, detail={"reasons": guard.reasons})

        asset_id = str(uuid.uuid4())
        etag = self.c.object_store.content_hash(data)
        vision = self.c.vision.recognize(filename or "label.png", data, page_limit=page_limit)

        s3_raw = self.c.object_store.put_bytes(
            "raw",
            asset_id,
            filename or f"label.{vision.source_format}",
            data,
            content_type or "application/octet-stream",
        )
        for i, page in enumerate(vision.page_images_png):
            self.c.object_store.put_bytes("normalized", asset_id, f"page-{i}.png", page, "image/png")
        extract = {
            "brand": vision.brand,
            "barcode": vision.barcode,
            "net_weight": vision.net_weight,
            "ingredients": vision.ingredients,
            "allergens": vision.allergens,
            "pages_processed": vision.page_count,
            "confidence": vision.confidence,
            "raw_ocr_text": vision.ocr_text,
        }
        s3_rec = self.c.object_store.put_json("recognized", asset_id, "extract.json", extract)
        self.c.object_store.put_json(
            "exports",
            asset_id,
            "pim_payload.json",
            {
                "asset_id": asset_id,
                "extract": extract,
                "schema_version": "1.0",
                "index_version": self.settings.index_version,
            },
        )

        doc_id = f"label-{asset_id[:8]}"
        self.c.store.upsert_document(
            DocumentNode(
                doc_id=doc_id,
                title=f"Label {vision.brand or asset_id[:8]}",
                corpus="product",
                classification="internal",
                allowed_roles=["store_associate", "category_manager", "compliance_officer"],
                text=vision.ocr_text,
                metadata={"modality": "ocr", "asset_id": asset_id},
            )
        )
        for a in vision.allergens:
            self.c.store.upsert_entity(a, "allergen", [doc_id])
        if vision.brand:
            self.c.store.upsert_entity(vision.brand, "brand", [doc_id])

        self.c.store.add_label_asset(
            LabelAssetNode(
                asset_id=asset_id,
                source_format=vision.source_format,
                page_count=vision.page_count,
                classification="internal",
                s3_uri_raw=s3_raw,
                s3_uri_recognized=s3_rec,
                s3_uri_normalized=f"s3://{self.settings.minio_bucket}/normalized/{asset_id}/",
                etag=etag,
                extract=extract,
            )
        )
        self.c.store.push_outbox(
            "label.recognized",
            {
                "asset_id": asset_id,
                "s3_uri_recognized": s3_rec,
                "s3_uri_raw": s3_raw,
                "schema_version": "1.0",
            },
        )

        state = await self.c.agent.arun(
            {
                "request_id": request_id,
                "message": f"Analyze label allergens {', '.join(vision.allergens)}",
                "modality": "label",
                "role": principal.role,
                "user_id": principal.user_id,
                "label_extract": extract,
                "errors": [],
            }
        )
        latency = int((time.perf_counter() - started) * 1000)
        metrics.VISION_LATENCY.observe(latency)
        record_request_audit(self.c, self.settings, request_id, principal, state, started, "label")
        metrics.REQUESTS.labels(endpoint="vision", status="ok").inc()

        warnings = []
        if vision.allergens:
            warnings.append(f"Detected allergens: {', '.join(vision.allergens)}")
        cfg = self.c.llm.get_config()
        return LabelResponse(
            asset_id=asset_id,
            extract=LabelExtract(**{**extract, "pages_processed": vision.page_count}),
            warnings=warnings,
            citations=[Citation(**x) for x in state.get("citations") or []],
            answer=state.get("answer", ""),
            s3_uri_raw=s3_raw,
            s3_uri_recognized=s3_rec,
            request_id=request_id,
            degraded=state.get("degraded", False),
            model_uri=state.get("model_uri") or cfg.model_uri,
            llm_provider=cfg.provider,
        )
