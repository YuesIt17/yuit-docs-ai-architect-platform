# Глоссарий

| Термин | Значение |
| ------ | -------- |
| GraphRAG | Гибридный retrieval: resolve по графу → векторный поиск с ACL |
| Control Plane | Auth, Guardrails, LangGraph-оркестратор, политики |
| Data Plane | Neo4j, Qdrant, MinIO, Postgres, Redis, LLM Serving |
| Air-gapped / closed loop | Без egress к SaaS LLM (OpenAI/Anthropic) |
| ACL на чанке | `classification` + `allowed_roles`; фильтр до LLM |
| LabelAsset | Файл этикетки + S3 URI (raw / recognized / export) |
| Paved Road | Golden-path compose demo stack |
| Soft degrade | Fallback при timeout LLM (`degraded=true`) |
| Semantic Cache | Кэш ответов после Output Guard; invalidate по `index_version` |
| LLM Serving | vLLM / Ollama / MOCK через OpenAI-compatible API |
| Outbox | Таблица событий (`label.recognized`) для PIM/ERP |
| Trust boundary | Граница BFF ↔ KP: только OpenAPI |

См. также: [hw-11 Glossary](../../yuit-docs-ai-architect/hw-11/Glossary.md).
