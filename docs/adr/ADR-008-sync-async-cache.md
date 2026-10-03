# ADR-008: Sync/Async + Semantic Cache

## Decision
- Sync/SSE for interactive chat and label extract
- Async `/v1/jobs` for batch/multi-hop
- Semantic cache after Output Guard; invalidate via `index_version` (hw-9)