# Sequence — распознавание этикетки (PDF/PNG)

## Назначение

Мультимодальный путь: upload → MIME guard → MinIO raw → OCR/VLM → recognized/exports → GraphRAG policy_check → outbox для PIM/ERP.

```mermaid
sequenceDiagram
  actor A as StoreAssociate
  participant GW as API
  participant VG as VisionGuard
  participant S3 as MinIO
  participant OCR as VisionOCR
  participant Orch as LangGraph
  participant G as GraphRAG
  participant PIM as Outbox_PIM

  A->>GW: POST /v1/vision/label multipart
  GW->>VG: MIME/size allowlist
  GW->>S3: put raw/
  GW->>OCR: normalize PDF/PNG + extract
  OCR-->>GW: structured JSON
  GW->>S3: put recognized/ + exports/
  GW->>Orch: label modality + allergens
  Orch->>G: policy retrieve ACL
  Orch-->>GW: grounded answer
  GW->>PIM: outbox label.recognized
  GW-->>A: LabelResponse + s3 URIs
```

См. [ADR-007](../adr/ADR-007-multimodal-labels.md), [data-flow.md](data-flow.md).
