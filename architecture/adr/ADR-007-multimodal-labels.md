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

Accept **PDF, PNG, JPEG, WEBP, TIFF**. Pipeline: MIME → rasterize PDF → OCR → structured JSON → policy_check (GraphRAG). Raw and recognized objects are stored in MinIO.

`OCR_PROVIDER` selects the engine:

- **RAPIDOCR:** PaddleOCR models on ONNX Runtime. The 14 MB of models ship inside the package, so it runs on CPU with no downloads, which fits the closed perimeter.
- **MOCK** (default): a deterministic pipeline contract for demos and CI without the OCR dependency.

An unknown provider fails at startup rather than silently falling back to the mock. The API and UI return the active `ocr_provider`, and MOCK responses carry a warning that nothing was read.

OCR text is untrusted input: PII is redacted, and prompts treat it as data rather than instructions.

## Consequences

- (+) Demonstrates the multimodal path contract; handoff through exports/outbox
- (+) Reads real labels locally, including blocks in non-linear layouts
- (−) Accuracy is verified only on generated labels; real photos with glare or curved packaging may need a vision model such as Qwen2-VL

## References

- Sequence: [sequence-label.md](../docs/sequence-label.md)
- ADR-009 (MinIO prefixes)
