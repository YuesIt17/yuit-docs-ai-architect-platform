# ADR-012: GenAI Gateway (LiteLLM)

## Status

Accepted

## Context

The platform needs an owned GenAI gateway for routing, failover, metering, and cost attribution across local serving (Ollama / vLLM / MOCK) and, later, demo multiprovider backends. ADR-001 keeps a **closed perimeter by default**. Product and agent code should keep using one OpenAI-compatible client.

## Selection criteria

- Optional: default path unchanged for CI and course demos
- OpenAI-compatible upstream for `LLMClient`
- Local aliases + documented failover
- Attribution fields (agent / team) in audit and metrics
- No live cloud keys required for CI

## Options

| Option | Pros | Cons |
| ------ | ---- | ---- |
| **LiteLLM proxy sidecar** | Matches JD “gateway on LiteLLM”; config-driven routing | Extra container |
| In-process LiteLLM SDK only | Fewer moving parts | Weaker “own the gateway” story |
| Custom router | Full control | Rebuild what LiteLLM already does |

## Decision

- Profiles:
  - `direct` (`LLM_GATEWAY=direct`, default) — ADR-001 client path
  - `gateway-local` — Compose LiteLLM → Ollama / mock aliases
  - `gateway-multiprovider` — same local aliases + stub Azure/Vertex/Bedrock entries (**runtime not verified** until exercised)
- Backend: when `LLM_GATEWAY=litellm`, `LLMClient` provider label is `LITELLM`, base URL is the proxy, model is an alias (`chat-default`, …)
- Allowlist still applies (`LLM_ALLOWED_BASE_URLS` includes LiteLLM URLs)
- Metering: Prometheus + audit rows carry `agent_id`, `team_id`, `gateway`, `model_route`

## Consequences

- (+) Closed default preserved; gateway is opt-in
- (+) Portfolio shows owned routing/metering without SaaS in CI
- (−) Live LiteLLM+Ollama stack is verified only when the Compose profile is actually run

## References

- Config: `app/infra/litellm/`
- Code: `kp/infrastructure/llm.py`, `kp/application/audit.py`
- Docs: [docs/agent-platform/genai-gateway.md](../../docs/agent-platform/genai-gateway.md)
