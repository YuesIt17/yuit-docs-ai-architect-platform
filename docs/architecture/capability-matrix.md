# Матрица capability (из hw-1…10)

| Capability | Источник | Статус MVP |
|------------|----------|------------|
| Sync vs Async API | hw-9 | Chat sync/SSE + `/v1/jobs` 202 |
| Semantic cache | hw-9 | Redis-ready in-memory stub + metric |
| Security chain | hw-6 | PII + injection + output ACL |
| Eval gates | hw-6/8 | `/evals` LLM-as-Judge stub + pytest |
| Canary / index_version | hw-8 | `INDEX_VERSION` / `POLICY_VERSION` |
| Data contracts | hw-5 | seed schema + outbox payload |
| Multi-agent SRP | hw-3 | LangGraph nodes/tools |
| OpenAPI boundary | hw-2 | `backend/openapi/...yaml` |
| Model Card / FinOps | hw-10 | docs + audit `cost_est` |
| Soft degrade | hw-9 | LLM failure → mock + `degraded=true` |
| Multimodal labels | итоговый MVP | PDF/PNG + MinIO |
| GraphRAG | критично | graph resolve + vector hybrid |
| Control/Data Plane | PE | сети compose + docs |

## Карточка SLO (цели дизайна MVP)

| Путь | SLI | Цель (учебный дизайн) |
|------|-----|------------------------|
| FAQ GraphRAG (mock LLM) | p95 latency | < 500 ms local |
| Label recognize (mock OCR) | p95 latency | < 1 s local |
| Availability | success rate | ≥ 99% в окне демо |
