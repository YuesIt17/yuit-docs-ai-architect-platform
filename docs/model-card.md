# Model Card — RetailPartnerX Knowledge Platform

Стыковка с [hw-10](../../yuit-docs-ai-architect/hw-10/) (Governance / FinOps). Учебный артефакт, не карточка модели на Hugging Face Hub.

## Intended use

Обоснованные (grounded) ответы для сотрудников магазина, category managers и compliance по Product / Policy / Regulatory KB и этикеткам упаковки.

## Вне scope

Медицинские советы, юридические заключения, обучение foundation-моделей с нуля.

## Модели

| Компонент | Default MVP |
|-----------|-------------|
| Chat LLM | MOCK или Qwen2.5/3-Instruct via vLLM/Ollama |
| Embeddings | Deterministic mock / multilingual-e5-base |
| Vision | Mock OCR; опционально Qwen-VL |

## Safety

RBAC на retrieval; input injection guard; output ACL; редакция PII в промптах/трейсах. Air-gapped: без OpenAI/Anthropic SaaS.

## Evaluation

Gold set в `/evals`; Faithfulness-style checks (пороги hw-6) — planned / stub LLM-as-Judge.

## Cost / FinOps

Audit `cost_est` на запрос; в CI предпочитать cache + MOCK. См. hw-10 Cost Optimization patterns (routing, TTL, distillation).

## Limitations

- Runtime GraphRAG MVP — in-memory mirror; Neo4j/Qdrant для демо/sync
- Demo tokens ≠ корпоративный IdP
- Качество OCR/VLM зависит от железа и не заявлено как prod accuracy
