# Executive Summary — RetailPartnerX Knowledge Platform

**Customer:** RetailPartnerX, a large FMCG retailer.  
**Role:** Platform Engineer / AI Architect, building an Internal Developer Platform for AI knowledge workloads.

## Problem

Unstructured knowledge (policies, regulatory excerpts, label scans) leads to hallucinations and lost context. Sensitive promo and margin documents must not leak between roles.

## Solution

An on-premises **GraphRAG Knowledge Platform**:

- **Control Plane:** AuthZ/RBAC, Input/Output Guardrails, LangGraph, ACL at retrieval
- **Data Plane:** Neo4j, Qdrant (Compose + in-memory MVP), MinIO, Postgres, Ollama/MOCK
- **Modalities:** text chat + label recognition (PDF/PNG/…)
- **Handoff:** JSON in MinIO `exports/` + `label.recognized` outbox → PIM/ERP

## Continuity

This project develops the case from `yuit-docs-ai-architect` (hw-1…hw-10) and the [hw-11](../../yuit-docs-ai-architect/hw-11/) pointer: dual KB, LangGraph, security layer, inference sizing, sync/async, FinOps/Model Card. **Reversal of hw-4:** self-hosted Ollama instead of SaaS.

## What the demo proves

1. `category_manager` does not receive the secret promo; `compliance_officer` does  
2. Label upload → OCR extract → policy citations  
3. Grafana LGTM (Tempo/Loki/Prom) + OTel + Neo4j Browser  

## Artifact map

| Section | Path |
| ------- | ---- |
| Assignment / criteria | [README](../README.md) |
| C4 / Deployment / Sequence / ER / Data Flow | [architecture/](../architecture/) · [diagram SVGs](../architecture/diagrams/images/) · [DIAGRAMS.md](DIAGRAMS.md) |
| Capacity Planning (VRAM / CPU / RAM) | [capacity-planning.md](capacity-planning.md) |
| ADR | [adr/](../architecture/adr/) |
| Demo / load | [video](https://www.youtube.com/watch?v=y2_mY9_ceuU) · [load-report.md](load-report.md) · [evidence/](evidence/) |
| Model Card | [model-card.md](model-card.md) |

Learning MVP: the GraphRAG runtime uses an in-memory mirror of the ontology; Neo4j/Qdrant run in Compose for the Browser and sync.
