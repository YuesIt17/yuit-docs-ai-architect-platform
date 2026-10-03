# FAANG Capability Matrix (from hw-1…10)

| Capability | Source HW | MVP status |
|------------|-----------|------------|
| Sync vs Async APIs | hw-9 | Chat sync/SSE + `/v1/jobs` 202 |
| Semantic cache | hw-9 | Redis-ready in-memory stub + metric |
| Security chain | hw-6 | PII + injection + output ACL |
| Eval gates | hw-6/8 | `/evals` LLM-as-Judge stub + pytest |
| Canary / index_version | hw-8 | `INDEX_VERSION` / `POLICY_VERSION` env |
| Data contracts | hw-5 | seed schema + outbox payload |
| Multi-agent SRP | hw-3 | LangGraph nodes/tools |
| OpenAPI boundary | hw-2 | `backend/openapi/...yaml` |
| Model Card / FinOps | hw-10 | docs + audit `cost_est` |
| Soft degrade | hw-9 | LLM failure → mock + `degraded=true` |
| Multimodal labels | course MVP | PDF/PNG path + MinIO |
| GraphRAG | course critical | Neo4j-style graph + vector hybrid |
| Control/Data Plane | PE | compose networks + docs |

## SLO card (targets)

| Path | SLI | Target (MVP design) |
|------|-----|---------------------|
| FAQ GraphRAG (mock LLM) | p95 latency | < 500 ms local |
| Label recognize (mock OCR) | p95 latency | < 1 s local |
| Availability | success rate | ≥ 99% in demo window |
