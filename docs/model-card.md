# Model Card — RetailPartnerX Knowledge Platform

Стыковка с [hw-10](../../yuit-docs-ai-architect/hw-10/) (Governance / FinOps). Учебный артефакт.

## Intended use

Обоснованные (grounded) ответы для сотрудников магазина, category managers и compliance по Product / Policy / Regulatory KB и демо-этикеткам.

## Вне scope

Медицинские советы, юридические заключения, обучение foundation-моделей, **реальный OCR** сложных PDF/сканов (отложен; текущий OCR = MOCK).

## Модели

| Компонент | Default MVP | Notes |
|-----------|-------------|-------|
| Chat LLM desktop | Ollama `qwen2.5:0.5b` | Convenience profile |
| Chat LLM submission | `Qwen/Qwen2.5-1.5B-Instruct-AWQ` via vLLM | AWQ, ctx 4096; **runtime не проверен** без GPU |
| Chat CI | MOCK | Deterministic |
| Embeddings | `intfloat/multilingual-e5-small` (384) or MOCK | LOCAL optional extra `.[embeddings]` |
| Vision / OCR | **MOCK** (`provider=MOCK`) | Pipeline contract demo only |

## Safety

RBAC на retrieval + asset presign; input injection guard; output ACL; PII redaction. Demo Bearer ≠ IdP. LLM URL allowlist (SEC-04).

## Evaluation

Deterministic ACL / GraphRAG pytest. LLM-as-Judge — optional local only, not a substitute for ACL tests.

## Cost / FinOps

Audit `cost_est`; cache-hit does not re-count inference tokens. Prefer MOCK in CI.

## Limitations

- OCR mock — not real document recognition
- Demo-auth
- vLLM GPU may be unverified
- Vault planned
- Session id ≠ dialog memory
