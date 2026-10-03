# ADR-002: Vector Database

## Decision
**Qdrant** self-hosted (compose). MVP also ships in-process vector index with identical ACL payload fields (`classification`, `allowed_roles`, `modality`, `index_version`) for CI without Docker.

## Trade-offs
Qdrant vs Milvus/Weaviate: simpler ops for retail MVP, strong payload filtering for RBAC.