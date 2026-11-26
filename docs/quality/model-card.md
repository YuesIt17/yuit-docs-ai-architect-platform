# Model Card — RetailPartnerX Knowledge Platform

Linked to [hw-10](../../yuit-docs-ai-architect/hw-10/) (Governance / FinOps). A learning artifact.

## Intended use

Grounded answers for store associates, category managers and compliance staff, based on the Product / Policy / Regulatory KB and demo labels.

## Out of scope

Medical advice, legal opinions and foundation model training.

## Models

| Component | Default MVP | Notes |
|-----------|-------------|-------|
| Chat LLM desktop | Ollama `qwen2.5:0.5b` | Convenience profile |
| Chat LLM submission | `Qwen/Qwen2.5-1.5B-Instruct-AWQ` via vLLM | AWQ, ctx 4096; **runtime not verified** without a GPU |
| Chat CI | MOCK | Deterministic |
| Embeddings | `intfloat/multilingual-e5-small` (384) or MOCK | LOCAL optional extra `.[embeddings]` |
| Vision / OCR | MOCK (default) or RapidOCR (PaddleOCR models on ONNX) | Set `OCR_PROVIDER=RAPIDOCR` for real reading; tested on generated labels only |

## Safety

RBAC at retrieval + asset presign; input injection guard; output ACL; PII redaction. Demo Bearer ≠ IdP by default; optional real login is in ADR-010. LLM URL allowlist (SEC-04).

## Evaluation

Deterministic ACL / GraphRAG pytest and a golden-set gate in CI. An optional local LLM judge (DeepEval) scores faithfulness and relevancy, and does not replace the ACL tests. See [evaluation.md](evaluation.md).

## Cost / FinOps

Audit `cost_est`; cache-hit does not re-count inference tokens. Prefer MOCK in CI.

## Limitations

- OCR accuracy on real label photos is not measured yet
- Demo-auth
- vLLM GPU may be unverified
- Vault rotation is not verified on a live cluster
- Dialog memory has no retention policy yet
