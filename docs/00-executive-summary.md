# RetailPartnerX Knowledge Platform — Executive Summary

**Customer:** RetailPartnerX — large global FMCG retailer (Tesco / Carrefour class).  
**Role:** Platform Engineer building an Internal Developer Platform (Google PE / SRE style) for AI knowledge workloads.

## Problem

Unstructured retail knowledge (policies, NPA abstracts, packaging labels as PDF/PNG scans) causes hallucinations and context loss in assistants. Sensitive promo/margin docs must not leak across roles.

## Solution

On-premise **GraphRAG Knowledge Platform**:

- **Control Plane:** API Gateway path, AuthZ/RBAC, Input/Output Guardrails, LangGraph orchestrator, ACL policy on retrieval
- **Data Plane:** Neo4j (graph), Qdrant-compatible vector index (in-memory MVP + compose service), MinIO (S3) for raw/recognized objects, Postgres audit, vLLM/Ollama/Mock LLM
- **Modalities:** text chat + label recognition (PDF/PNG/JPEG/WEBP/TIFF)
- **Handoff:** recognized JSON in MinIO `exports/` + outbox event `label.recognized` for PIM/ERP

## Continuity

Evolves the RetailPartnerX case study from `yuit-docs-ai-architect` (hw-1…hw-10): dual KB, LangGraph, security layer, vLLM sizing, sync/async, FinOps/Model Card.

## Demo proofs

1. `category_manager` cannot retrieve secret promo margin doc; `compliance_officer` can  
2. Label upload → OCR extract → policy citations  
3. Jaeger/OTel + Prometheus metrics + Neo4j Browser (compose profile)