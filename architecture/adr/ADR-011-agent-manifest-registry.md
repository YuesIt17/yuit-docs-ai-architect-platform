# ADR-011: Agent Manifest & Registry

## Status

Accepted

## Context

Product teams and peer agents need a **single declarative specification** that wires an agent into the platform (skills, tools, memory, model, guardrails, sandbox, security, triggers). The course MVP had a fixed LangGraph GraphRAG agent with no registry. The Agent Platform roadmap ([docs/agent-platform/roadmap.md](../../docs/agent-platform/roadmap.md)) makes the manifest/registry the first control-plane slice.

## Selection criteria

- One schema for disk and API registration
- Existing GraphRAG chat remains the first reference agent without a rewrite
- Role-gated invoke and resolve
- Practical HTTP API for discovery and demos
- No Kubernetes CRD yet (Phase 7)

## Options

| Option | Pros | Cons |
| ------ | ---- | ---- |
| **In-process YAML registry + FastAPI** | Fast to ship, testable, matches monorepo | Not multi-replica consistent for API POSTs |
| ConfigMaps / CRD only | K8s-native | Heavier; blocks local pytest UX |
| ADK-only registry | Aligns with Google ADK JD | Would replace LangGraph course agent |

## Decision

- Manifest schema: `apiVersion: kp.retailpartnerx/v1`, `kind: Agent` (Pydantic in `kp/agents/manifest.py`)
- Disk source: `app/backend/agents/*.yaml` (override with `AGENT_MANIFESTS_DIR`)
- Runtime registry: `AgentRegistry` on `AppContainer`; API registrations are **in-memory** until restart
- Reference agents on disk: `graphrag-chat` (LangGraph) and `label-assistant` (stub / vision trigger)
- HTTP: `GET/POST /v1/agents`, `GET …/resolve`, `POST …/invoke`
- `/v1/chat` authorizes `DEFAULT_AGENT_ID` (default `graphrag-chat`) or `ChatRequest.agent_id`

## Consequences

- (+) Portfolio demonstrates agent control-plane ownership without breaking the eval gate
- (+) Product teams can add a YAML file and see it listed immediately
- (−) API `POST /v1/agents` is not durable across replicas/restarts (document; CRD later)
- (−) Non-`langgraph` invoke returns 501 until later phases wire ADK/MCP

## References

- Code: `kp/agents/`, `kp/api/agents.py`, `app/backend/agents/`
- How-to: [docs/agent-platform/agents.md](../../docs/agent-platform/agents.md)
- Tests: `tests/test_agent_registry.py`
