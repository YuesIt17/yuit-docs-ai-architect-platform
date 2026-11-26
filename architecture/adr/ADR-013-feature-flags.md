# ADR-013: Feature Flags (Flagd / OpenFeature)

## Status

Accepted

## Context

Prompts, model routes, and agent availability need progressive rollout and an emergency kill-switch with an audit trail. Env toggles alone are not enough for percentage targeting or safe stop of autonomous agents.

## Selection criteria

- Kill-switch reliable in the chat/invoke path
- Same flag definitions for CI (in-memory) and desktop (Flagd)
- OpenFeature-shaped evaluation API
- No SaaS flag vendor required for CI

## Options

| Option | Pros | Cons |
| ------ | ---- | ---- |
| **Flagd + in-process evaluator** | CNCF/OpenFeature aligned; file-based | Extra container for live demo |
| Env-only flags | Simple | No progressive rollout |
| SaaS flag product | Rich UI | Not closed-perimeter friendly |

## Decision

- Flag keys: `kill_switch_agents`, `agent_enabled`, `prompt_version`, `model_route`
- Definitions: `app/infra/flagd/flags.json` (fractional targeting on prompt/model)
- Runtime: `FeatureFlagService` with in-memory provider by default; OFREP HTTP client when `FLAGD_URL` is set
- Kill-switch / `agent_enabled=false` → HTTP 503, audit `acl_decision=deny_kill_switch`
- Effective `prompt_version` and `model_route` recorded on audit rows and used for LiteLLM alias when gateway is on

## Consequences

- (+) Demo kill-switch without redeploy
- (+) CI stays offline (loads the same JSON)
- (−) API `POST` overrides of Flagd state are out of scope; flip flags via file/Flagd UI/API

## References

- Code: `kp/infrastructure/feature_flags.py`
- Docs: [docs/agent-platform/feature-flags.md](../../docs/agent-platform/feature-flags.md)
- Compose profile: `flags` in `app/infra/docker-compose.yml`
