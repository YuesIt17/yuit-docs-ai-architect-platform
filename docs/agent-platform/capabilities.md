# Agent Platform Capability Map

This is the **capability inventory** for Coraium Agent Platform. RetailPartnerX is the first existing retail reference implementation. Read with [roadmap](./roadmap.md), [public architecture views](./public-architecture.md), [open-source strategy](./open-source-strategy.md), [engineering standards](./engineering/README.md), and [delivery workflow](./delivery-workflow.md).

**Status vocabulary:** `implemented` = code exists; `verified` = reproducible recorded test; `planned` = not implemented; `optional` = no commitment without a use case. A mocked unit test is not live runtime verification.

## Core platform

| Capability | Existing foundation | Required outcome / gap | Priority |
| --- | --- | --- | --- |
| Registry and admission | AgentManifest, in-process registry, API, role checks. GraphRAG invoke admits only `kp.agent.graph:KnowledgeAgent` and builtin `graph_retrieve` / `vector_retrieve` (unit-tested) | Sandbox network and process isolation remain declarative. Durable/replicated registry only if needed | P0 |
| Orchestrator choice | Existing LangGraph GraphRAG; manifest has `runtime` | Optional local Google ADK reference agent behind same external API; no checkpoint portability claim | P1 |
| Agent tools and interoperability | Retrieval nodes, declarative tool schema, SSE | Enforced tool allowlist and scoped identity first; MCP for one read-only tool; A2A/AG-UI when justified | P0/P2 |
| Model gateway | Direct client and LiteLLM profiles, aliases, attribution. Desktop proxy + mock aliases verified. Request-scoped alias and ungrounded outage/mock answers are unit-tested | Live Ollama-primary smoke, measured usage/budget, and a recorded egress check | P0 |
| Progressive rollout | Flagd/in-memory evaluator, kill-switch at admission. OFREP timeout or error fails closed for new runs (unit-tested) | Live Flagd smoke, safe mid-run cancellation, verified rollout and rollback | P0 |
| Durable execution | LangGraph checkpoints, PostgreSQL and Celery ingestion | Agent run ledger, retries, approval, recovery, idempotent side effects; Temporal optional | P1 |
| Identity/permissions | Role ACL, Keycloak/Go BFF option | Agent identity, delegated user scopes, tool-level authorization and credential isolation | P0/P1 |
| Secrets | Vault + External Secrets Operator templates, dynamic PostgreSQL DSN design | End-to-end rotation/revocation verification, no secrets in logs or agent manifests | P1 |
| Reliability | OTel/LGTM, load tests, SRE documentation | Agent SLIs/SLOs, gateway failure drill, dashboards, actionable runbooks | P1 |
| Quality feedback | Golden-set/ACL gates, DeepEval-shaped judge, OTel | Scrub trace → review → labeled dataset → CI regression; real local judge evidence | P1 |
| Knowledge and artifacts | GraphRAG, Neo4j, Qdrant, MinIO, session checkpoints | Provenance-aware document model, lifecycle/retention, optional scoped long-term memory | P1 |
| Regulated-data readiness | Closed default, ACL, audit and K8s hardening | Durable audit, privacy-by-design, deletion/retention, boundaries/controls evidence | P1 |

## Multi-domain expansion (proposals, not shipped)

Source of truth for the intended split and sequence: [multi-domain architecture](./multi-domain-architecture.md). Preferred default: **LangGraph / Domain Intelligence** and **Google ADK / Engineering & Governance**, with per-agent runtime choice rather than a domain-enforced framework lock. **A2A cross-runtime collaboration is planned**, not currently supported. Registry manifests, tools and checkpoints do not by themselves prove A2A interoperability.

| Capability / domain | Existing foundation | Next evidence / safeguard | Priority |
| --- | --- | --- | --- |
| Retail GraphRAG (LangGraph) | Existing retail knowledge workflow, ACL-aware retrieval | Preserve behavior; expose a scoped A2A evidence-lookup endpoint only when the cross-system use case is ready | P0/P2 |
| Google ADK Policy/DevSecOps track | Optional ADK runtime in roadmap; not implemented | Self-hosted independent read-only reviewer, approved tools, policy enforcement, shared gateway/OTel | P1 |
| LangGraph ↔ ADK over A2A | No verified A2A endpoint or protocol exchange | Agent Cards, identity-scoped task delegation, status/results/artifacts, timeouts, denial and trace tests | P2 |
| LangGraph Nutrition and Fitness | General retrieval/agent foundations | Synthetic-data end-to-end Food → Nutrition → Fitness with grounded ingredient evidence and safe uncertainty | P2 |
| LangGraph Health Evidence | General GraphRAG/security foundations only | Educational evidence lookup, citations, safety evals, no diagnosis/treatment | P2 |
| Healthcare regulated-data readiness | Closed default, ACL, optional Keycloak/Vault | Separate patient/tenant/purpose/consent boundaries, retention/deletion, legal/privacy/clinical risk gate; FHIR only if needed | Later |
| ADK Compliance, Approval, Policy Research | Existing general platform controls | Delegate analysis only; deterministic policy decision and trusted approval backend for sensitive actions | P2 |

**Personal Life Assistant** (food, wellness, fitness) and **Enterprise Agent Platform** (retail, governance, possible healthcare later) are product concepts, not currently shipped offerings. Keep health data isolated and never imply regulatory certification.

## Product and document intelligence

| Capability | Existing | Carefully scoped improvement |
| --- | --- | --- |
| Image/label OCR | RapidOCR ONNX on CPU; MOCK CI mode; PDF rasterization; ADR-007 | Benchmark on real permitted samples; image preprocessing and confidence/failure reporting |
| Structured PDF extraction | Existing PDF/image ingest | Evaluate optional **Docling** adapter for tables, reading order, page coordinates and structure; keep RapidOCR for light CPU OCR |
| Normalized documents | MinIO raw/recognized/export, GraphRAG ingestion | Canonical parsed document with text, table, page, bbox, source hash, parser version, classification and citation provenance |
| Retrieval quality | Vector/graph hybrid, semantic cache and ACL checks | Chunking by structure, no leakage on caches, offline retrieval quality dataset, measurable latency/accuracy trade-offs |
| OCR parser choice | Current RAPIDOCR/MOCK switch | Benchmark before adopting Docling; LlamaIndex is an indexing/RAG integration option, **not a required OCR engine** |

Prefer **one** additional parser when measurements justify it; no default cloud OCR, no speculative VLM stack.

## Platform foundation versus vendor adapters

| Need | Existing choice | Do not add until needed |
| --- | --- | --- |
| Runtime | LangGraph, optional Google ADK | Other agent frameworks |
| Serving | Ollama local; optional self-hosted vLLM + LiteLLM | Three managed clouds, KV-aware routing without GPU evidence |
| Orchestration | LangGraph checkpoints, PostgreSQL, existing Celery for ingestion | Temporal, CRD/operator unless run lifecycle needs them |
| Observability | OpenTelemetry, Prometheus, Grafana, Loki, Tempo | Datadog/Braintrust solely for brand matching |
| Evaluation | Golden sets, security tests, optional DeepEval | MLflow unless comparisons/registry justify it |
| Deployment | Compose, Docker, Helm, K8s; AWS IaC not runtime-verified | Kustomize overlays without a concrete configuration need |
| Secrets | Vault + ESO templates | Another secrets manager |
| Frontend | React/TypeScript/Vite | New framework/bundler |
| Specification | Markdown roadmap/ADRs | Separate GitHub Wiki or mandatory tooling for trivial changes |

See [Roadmap](./roadmap.md) for sequence, owner-independent acceptance criteria, and explicit non-goals.

## Evidence matrix for interviews

Every capability should have: linked code, test, whether test used MOCK or real runtime, negative/failure scenario, observed metric/trace where applicable, and a candid limit. Avoid claims of production healthcare compliance, large-scale operation, live cloud routing or ADK support before demonstrated.
