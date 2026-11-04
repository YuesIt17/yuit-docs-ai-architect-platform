# ADR-008: Sync / Async and Semantic Cache

## Status

Accepted

## Context

Interactive chat and label recognition need low latency (sync/SSE). Heavy multi-hop and batch work is async. Continuity with hw-9: the semantic cache reduces RPS to the LLM.

## Selection criteria

- Sync for chat UX
- Async for batch
- Cache invalidation when the index changes
- Cache only after the Output Guard (never cache leaks)

## Options

| Option | Pros | Cons |
| ------ | ---- | ---- |
| Everything sync | Simple | Timeouts on heavy work |
| Everything async | Scale | Poor chat UX |
| **Sync/SSE + async jobs + semantic cache** | Balanced | Two API paths |

## Decision

- Sync/SSE for interactive chat and label extraction
- Async `/v1/jobs` for batch / multi-hop
- Semantic cache **after** the Output Guard; invalidation through `index_version` (hw-9)

## Consequences

- (+) Lower LLM OpEx; UX preserved
- (−) Risk of a stale cache if versioning is wrong

## References

- hw-9 high-load architecture
- Redis in the Data Plane
