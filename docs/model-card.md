# Model Card — RetailPartnerX Knowledge Platform

Linked to [hw-10](../../yuit-docs-ai-architect/hw-10/) (Governance / FinOps). A learning artifact.

## Intended use

Grounded answers for store associates, category managers and compliance staff, based on the Product / Policy / Regulatory KB and demo labels.

## Out of scope

Medical advice, legal opinions, foundation model training, and **real OCR** of complex PDFs/scans (deferred; the current OCR is MOCK).

## Models

| Component | Default MVP | Notes |
|-----------|-------------|-------|
| Chat LLM desktop | Ollama `qwen2.5:0.5b` | Convenience profile |
| Chat LLM submission | `Qwen/Qwen2.5-1.5B-Instruct-AWQ` via vLLM | AWQ, ctx 4096; **runtime not verified** without a GPU |
| Chat CI | MOCK | Deterministic |
| Embeddings | `intfloat/multilingual-e5-small` (384) or MOCK | LOCAL optional extra `.[embeddings]` |
| Vision / OCR | **MOCK** (`provider=MOCK`) | Pipeline contract demo only |

## Safety

RBAC at retrieval + asset presign; input injection guard; output ACL; PII redaction. Demo Bearer ≠ IdP. LLM URL allowlist (SEC-04).

## Evaluation

Deterministic ACL / GraphRAG pytest and a golden-set gate in CI. An optional local LLM judge (DeepEval) scores faithfulness and relevancy, and does not replace the ACL tests. See [evaluation.md](evaluation.md).

## Cost / FinOps

Audit `cost_est`; cache-hit does not re-count inference tokens. Prefer MOCK in CI.

## Limitations

- OCR mock — not real document recognition
- Demo-auth
- vLLM GPU may be unverified
- Vault planned
- Session id ≠ dialog memory
