# Knowledge Platform Glossary

Terms as used in the RetailPartnerX Knowledge Platform (KP).

### GraphRAG

Hybrid retrieval: first resolve entities and relationships in the knowledge graph (Neo4j / in-memory mirror), then run vector search over chunks with an ACL filter. The goal is fewer hallucinations and less context loss than a "bag of embeddings". See [ADR-003](../architecture/adr/ADR-003-graph-db.md), [data-flow](../architecture/docs/data-flow.md).

### Control Plane

The request management layer: AuthN/RBAC, Input/Output Guardrails, the LangGraph orchestrator, policies and the semantic cache. It stores no raw knowledge blobs; it decides *who* gets an answer and *how*. See [c4-container](../architecture/docs/c4-container.md).

### Data Plane

Storage and inference: Neo4j, Qdrant, MinIO, Postgres, Redis, LLM Serving (Ollama/MOCK). It is isolated from the edge, and access goes through the Control Plane. In the hybrid setup, stores live in K8s and Ollama/observability in Compose.

### Air-gapped / closed loop

A mode with no egress to SaaS LLMs (OpenAI, Anthropic and similar). Answers come only from self-hosted Ollama or MOCK. See [ADR-001](../architecture/adr/ADR-001-llm-serving.md).

### Chunk-level ACL

`classification` + `allowed_roles` metadata on a chunk/node. The filter runs **before** context reaches the LLM, so User B cannot see a secret document. Demo: manager vs compliance. See [ADR-005](../architecture/adr/ADR-005-security.md).

### LabelAsset

The multimodal label artifact: the source file + URIs in the object store (`raw` / `recognized` / `export`). Pipeline: upload → OCR/vision extract → policy citations → JSON for PIM. See [ADR-007](../architecture/adr/ADR-007-multimodal-labels.md).

### Paved Road

The golden path for bringing up the demo: hybrid Compose (Ollama + observability) + K8s (api/frontend/stores), with no duplicate services. Entry point: `make demo` / [`docs/SETUP.md`](SETUP.md).

### Soft degrade

On an LLM timeout or outage, the API responds with a fallback (MOCK) and a `degraded=true` flag instead of a hard 5xx. This preserves the demo and UX when inference fails. See [ADR-008](../architecture/adr/ADR-008-sync-async-cache.md).

### Semantic Cache

A cache of finished answers **after** the Output Guard; the key accounts for the role and index version (`index_version`). It is invalidated when policies or the index change. See [ADR-008](../architecture/adr/ADR-008-sync-async-cache.md).

### LLM Serving

The token-serving layer: Ollama (OpenAI-compatible API) or MOCK for tests and demos without a model. The provider and URL are set at runtime (`LLM_PROVIDER`, base URL). See [ADR-001](../architecture/adr/ADR-001-llm-serving.md).

### Outbox

An event table/stream (for example `label.recognized`) for reliably passing results to PIM/ERP without a direct synchronous link. See [ADR-009](../architecture/adr/ADR-009-object-store.md), [data-flow](../architecture/docs/data-flow.md).

### Trust boundary

The BFF ↔ Knowledge Platform trust boundary: only OpenAPI (and SSE chat) is exposed outside; internal stores and the LLM are not reachable from the DMZ. See [c4-context](../architecture/docs/c4-context.md), [deployment](../architecture/docs/deployment.md).
