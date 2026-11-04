# Capability Matrix (from hw-1…10)

| Capability | Source | MVP status |
|------------|----------|------------|
| Sync vs Async API | hw-9 | Chat sync/SSE + `/v1/jobs` 202 |
| Semantic cache | hw-9 | Off by default; hit re-auths sources (SEC-01) |
| Security chain | hw-6 | PII + injection + output ACL + asset ACL |
| Eval gates | hw-6/8 | Deterministic pytest; no `app/evals/` folder |
| Canary / index_version | hw-8 | `INDEX_VERSION` / `POLICY_VERSION` / `PROMPT_VERSION` |
| Data contracts | hw-5 | seed schema + outbox payload |
| Multi-agent SRP | hw-3 | LangGraph **state machine** (not autonomous ReAct) |
| OpenAPI boundary | hw-2 | FastAPI OpenAPI |
| Model Card / FinOps | hw-10 | docs + audit `cost_est` |
| Soft degrade | hw-9 | LLM failure → mock + `degraded=true` |
| Multimodal labels | final MVP | **OCR provider=MOCK**; real OCR deferred |
| GraphRAG | critical | graph resolve + vector hybrid + graph-on/off |
| Serving | hw-7 | Ollama desktop + vLLM AWQ profile (GPU may be unverified) |
| Control/Data Plane | PE | compose + Helm + NetworkPolicy templates |
| Video | course | [YouTube](https://www.youtube.com/watch?v=y2_mY9_ceuU) |

## SLO Card (MVP design targets)

| Path | SLI | Target (learning design) |
|------|-----|------------------------|
| FAQ GraphRAG (mock LLM) | p95 latency | < 500 ms local |
| Label recognize (mock OCR) | p95 latency | < 1 s local |
| Availability | success rate | ≥ 99% within the demo window |

Measurements: `scripts/load_smoke.py` is a smoke test, not a capacity test.
