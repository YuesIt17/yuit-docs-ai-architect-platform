# ADR-007: Multimodal Label Recognition

## Status

Accepted

## Context

RetailPartnerX processes label scans (PDF, PNG and others). The platform must extract structure, link it to policies through GraphRAG and hand off to PIM/ERP.

## Selection criteria

- Support for common label formats
- Separate raw / recognized / export areas in the object store
- CI without heavy OCR (fixtures / mock)
- Policy check after extraction

## Options

| Option | Pros | Cons |
| ------ | ---- | ---- |
| End-to-end VLM only | Shorter pipeline | Expensive on GPU, weaker audit |
| **Detect → rasterize → OCR/VLM → JSON → GraphRAG** | Control over each step | More components |
| Manual annotation | Quality | Does not scale |

## Decision

Accept **PDF, PNG, JPEG, WEBP, TIFF**. Pipeline: MIME → rasterize PDF → **OCR provider=MOCK** extract → structured JSON → policy_check (GraphRAG). Raw and recognized objects are stored in MinIO. CI uses deterministic fixtures.

**Real OCR** of complex scans/drawings is **outside the current MVP** (a known deviation that requires separate agreement). The API and UI explicitly return `ocr_provider=MOCK`. The mock must not be presented as real document recognition.

## Consequences

- (+) Demonstrates the multimodal path contract; handoff through exports/outbox
- (−) No production OCR accuracy; meeting the course's overall OCR goal remains a risk until agreed

## References

- Sequence: [sequence-label.md](../docs/sequence-label.md)
- ADR-009 (MinIO prefixes)
