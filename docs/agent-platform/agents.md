# Agent manifests and registry

Phase 1 control plane: a **declarative Agent YAML** plus an in-process registry that product surfaces, `/v1/chat`, and (later) A2A can discover.

ADR: [ADR-011](../../architecture/adr/ADR-011-agent-manifest-registry.md).

## What ships today

| Agent id | Runtime | How to use |
| -------- | ------- | ---------- |
| `graphrag-chat` | LangGraph | `POST /v1/chat` or `POST /v1/agents/graphrag-chat/invoke` |
| `label-assistant` | stub | Discover via registry; call `POST /v1/vision/label` (invoke endpoint returns 501) |

Manifests live in [`app/backend/agents/`](../../app/backend/agents/).

## Try it (API up, demo auth)

```powershell
$H = @{ Authorization = "Bearer compliance" }

# List reference agents
Invoke-RestMethod -Headers $H http://127.0.0.1:8080/v1/agents

# Full manifest
Invoke-RestMethod -Headers $H http://127.0.0.1:8080/v1/agents/graphrag-chat

# Live bindings (model URI, memory backend, tools)
Invoke-RestMethod -Headers $H http://127.0.0.1:8080/v1/agents/graphrag-chat/resolve

# Invoke through the registry (non-streaming)
Invoke-RestMethod -Method Post -Headers $H `
  -ContentType "application/json" `
  -Uri http://127.0.0.1:8080/v1/agents/graphrag-chat/invoke `
  -Body '{"message":"gluten allergen policy","stream":false}'
```

With curl:

```bash
curl -s -H "Authorization: Bearer compliance" http://127.0.0.1:8080/v1/agents | jq .
curl -s -H "Authorization: Bearer compliance" \
  http://127.0.0.1:8080/v1/agents/graphrag-chat/resolve | jq .
curl -s -H "Authorization: Bearer compliance" \
  -H "Content-Type: application/json" \
  -d '{"message":"gluten allergen policy","stream":false}' \
  http://127.0.0.1:8080/v1/agents/graphrag-chat/invoke
```

## Add a new agent (product team)

1. Copy [`app/backend/agents/graphrag-chat.yaml`](../../app/backend/agents/graphrag-chat.yaml) to `app/backend/agents/<id>.yaml`.
2. Change `metadata.id`, `display_name`, skills/tools/triggers. Keep `apiVersion` / `kind`.
3. Restart the API (disk load happens at process start).
4. Confirm: `GET /v1/agents` includes your id.
5. If `runtime: langgraph` and the entrypoint is already wired like GraphRAG, use `POST /v1/agents/<id>/invoke`. Otherwise leave invoke for a later phase and document the real API path under `triggers`.

### Runtime registration (demo only)

`POST /v1/agents` accepts a full manifest JSON (role **compliance_officer** only). Registrations are **in-memory** and disappear on restart — use YAML on disk for anything you want to keep.

```powershell
$manifest = Get-Content app/backend/agents/graphrag-chat.yaml -Raw
# Prefer JSON body from OpenAPI schema; YAML-on-disk is the durable path.
```

## Settings

| Env | Default | Meaning |
| --- | ------- | ------- |
| `AGENT_MANIFESTS_DIR` | `<backend>/agents` | Directory of `*.yaml` / `*.yml` |
| `DEFAULT_AGENT_ID` | `graphrag-chat` | Agent used by `/v1/chat` when `agent_id` is omitted |

## Schema (fields)

Top-level: `apiVersion`, `kind`, `metadata`, `spec`.

`spec` includes: `runtime` (`langgraph` \| `adk` \| `stub`), `entrypoint`, `enabled`, `skills[]`, `tools[]`, `memory`, `model`, `guardrails`, `sandbox`, `security`, `triggers[]` (`api` \| `a2a` \| `schedule`).

Validation is enforced by Pydantic (`kp.agents.manifest.AgentManifest`) on load and on `POST /v1/agents`.

## What invoke actually enforces

`/v1/chat` and `/v1/agents/{id}/invoke` admit a run only when all of the following hold:

| Check | Result |
| ----- | ------ |
| Unknown id | 404 |
| Disabled manifest | 503 |
| Role not in `required_roles` | 403 |
| Blank bearer token | 401. In demo auth, a missing header is the guest principal, not an anonymous bypass |
| `runtime` other than `langgraph` | 501. `label-assistant` stays on `POST /v1/vision/label` |
| `entrypoint` other than `kp.agent.graph:KnowledgeAgent` | 403 on invoke. `POST /v1/agents` returns 422. The string is not imported |
| Tools other than builtin `graph_retrieve` and `vector_retrieve` | 403 |
| LiteLLM `model_route` other than `chat-default` or `chat-mock` | 403 before the model call |

`graphrag-chat` matches the allowlist, so its retrieve and ACL behavior is unchanged. There is no tenant id. Clearance is the existing role map (guest cannot read secret documents).

`sandbox.network` and process isolation are **declarative**. This slice does not add a sandbox, gVisor, or a network policy of its own. Disk YAML may still describe a stub agent with another entrypoint; that agent is not executed through chat invoke.

## Tests

```powershell
cd app/backend
OTEL_SDK_DISABLED=true .\.venv\Scripts\python.exe -m pytest -q tests/test_agent_registry.py
```
