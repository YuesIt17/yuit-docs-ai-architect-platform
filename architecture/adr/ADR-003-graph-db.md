# ADR-003: Graph Database

## Status

Accepted

## Context

Plain vector search does not satisfy the course's GraphRAG criterion. RetailPartnerX needs an ontology of corporate knowledge (documents, chunks, entities, topics, labels) and relationship edges for multi-hop resolution before dense search.

## Selection criteria

- Self-hosted graph with a Browser for the demo
- Simple ontology of 4–5 node types
- Cypher and visualization for the project defense
- Model mirrored in the in-memory MVP

## Options

| Option | Pros | Cons |
| ------ | ---- | ---- |
| **Neo4j Community** | Browser, Cypher, mature ecosystem | JVM footprint |
| Memgraph | Fast in-memory | Less learning material |
| Nebula | Scale-out | Excessive for an MVP |

## Decision

**Neo4j Community** for the GraphRAG ontology:

- Nodes: `Document`, `Chunk`, `Entity`, `Topic`, `LabelAsset`
- Edges: `CONTAINS`, `REFERENCES`, `ABOUT`, `AMENDS`, `HAS_ALLERGEN`, `GOVERNS`, `EXTRACTED_FROM`, `DESCRIBES_SKU`

**MVP runtime:** an in-memory graph with the same model; Compose Neo4j serves the Browser demo and sync pipelines. This meets the GraphRAG requirement without falsely claiming live Cypher on every chat.

## Consequences

- (+) Explicit relationships reduce context loss compared with a "bag of chunks"
- (−) Requires ingest/ontology discipline; memory↔Neo4j dual writes as the system grows

## References

- ER: [er-diagram.md](../docs/er-diagram.md)
- `app/backend/kp/repositories/memory_store.py`, `pipelines/sync_neo4j.py`
