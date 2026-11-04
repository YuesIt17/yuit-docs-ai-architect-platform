# ADR-002: Vector Database

## Status

Accepted

## Context

RAG over policies, label chunks and documents needs a self-hosted vector index with **ACL payload filtering** (`classification`, `allowed_roles`) applied before context reaches the LLM.

## Selection criteria

- Self-hosted, no managed cloud DB
- Query-time payload filters
- Simple ops for the MVP / Compose
- CI compatibility without Docker (in-process fallback)

## Options

| Option | Pros | Cons |
| ------ | ---- | ---- |
| **Qdrant** | Simple Compose setup, strong payload filters | Fewer enterprise features than Milvus |
| Milvus | Scale, GPU index | Heavier ops |
| Weaviate | Modules, hybrid search | More complex schema for an MVP |
| pgvector | Single Postgres instance | Weaker for dense ANN at scale |

## Decision

**Qdrant**, self-hosted (Compose). The MVP also keeps an **in-process** vector index with the same ACL fields for CI without Docker. Pipelines sync Compose Qdrant for the demo; in the MVP, runtime chat reads the in-memory mirror (an explicit trade-off for a learning project).

## Consequences

- (+) Fast ACL path at retrieval; lightweight demo stack
- (−) Requires discipline to keep the payload schema and graph in sync; live Qdrant on every chat is a post-MVP stage

## References

- `app/backend/kp/repositories/memory_store.py`
- Compose: `app/infra/docker-compose.yml`
