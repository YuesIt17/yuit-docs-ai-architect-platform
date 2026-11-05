# Architecture Decision Records

ADR registry for the RetailPartnerX Knowledge Platform. Format: Status → Context → Criteria → Options → Decision → Consequences.

| # | Topic | Status |
| - | ----- | ------ |
| [ADR-001](ADR-001-llm-serving.md) | LLM Serving (Ollama / vLLM / MOCK) | Accepted |
| [ADR-002](ADR-002-vector-db.md) | Vector DB (Qdrant + in-memory MVP) | Accepted |
| [ADR-003](ADR-003-graph-db.md) | Graph DB (Neo4j + GraphRAG ontology) | Accepted |
| [ADR-004](ADR-004-orchestration.md) | Orchestration (LangGraph) | Accepted |
| [ADR-005](ADR-005-security.md) | Security & RBAC / Guardrails | Accepted |
| [ADR-006](ADR-006-observability.md) | Observability (LGTM: Tempo, Loki, Prom, Grafana) | Accepted |
| [ADR-007](ADR-007-multimodal-labels.md) | Multimodal labels | Accepted |
| [ADR-008](ADR-008-sync-async-cache.md) | Sync/Async + Semantic Cache | Accepted |
| [ADR-009](ADR-009-object-store.md) | Object Store (MinIO) | Accepted |
| [ADR-010](ADR-010-bff-auth.md) | Real login: Keycloak and a Go BFF | Accepted, optional |
