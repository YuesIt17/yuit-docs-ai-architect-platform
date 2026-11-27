# Feature flags (Flagd / OpenFeature)

Progressive rollout for prompts, model routes, and an emergency **kill-switch** for agents. CI uses an in-memory provider loaded from the same definitions file; Compose profile `flags` runs Flagd. Shared request path: [genai-gateway.md](./genai-gateway.md).

ADR: [ADR-013](../../architecture/adr/ADR-013-feature-flags.md).

## Flag keys

| Key | Type | Default | Purpose |
| --- | ---- | ------- | ------- |
| `kill_switch_agents` | bool | `false` | Emergency stop — block chat/invoke, audit `deny_kill_switch` |
| `agent_enabled` | bool | `true` | Disable agent invoke without full kill-switch |
| `prompt_version` | string | `v1` | Progressive prompt variant (90/10 fractional in Flagd file) |
| `model_route` | string | `chat-default` | LiteLLM / alias selection (`chat-mock` canary) |

Definitions: [`app/infra/flagd/flags.json`](../../app/infra/flagd/flags.json).

## Run Flagd (desktop)

```powershell
cd app/infra
docker compose --profile flags up -d flagd
```

```env
FLAGD_URL=http://127.0.0.1:8016
# FEATURE_FLAGS_FILE=  # optional override; default is app/infra/flagd/flags.json
FEATURE_FLAGS_ENABLED=true
```

When `FLAGD_URL` is empty, the API evaluates defaults from the JSON file (deterministic; fractional targeting is not applied in-process).

When `FLAGD_URL` is set and Flagd times out or returns an error, **security flags fail closed**: new `/v1/chat` and `/v1/agents/{id}/invoke` calls return **503** with audit `acl_decision=deny_kill_switch` and `flag_provider=flagd_unavailable`. `prompt_version` and `model_route` stay on the file defaults and do not allow the turn. This is admission-time only. An in-flight graph run is not cancelled. Live Flagd is **not verified** until the Compose profile below is exercised. In-process tests cover the timeout and HTTP-error paths.

## Kill-switch demo

With the API up (demo auth):

```powershell
$H = @{ Authorization = "Bearer compliance" }

# Normal chat
Invoke-RestMethod -Method Post -Headers $H -ContentType "application/json" `
  -Uri http://127.0.0.1:8080/v1/chat `
  -Body '{"message":"gluten allergen policy","stream":false}'
```

In tests / local process, force the in-memory override (see `tests/test_feature_flags.py`):

1. `flags.override("kill_switch_agents", True)` → `POST /v1/chat` returns **503**
2. Audit row: `acl_decision=deny_kill_switch`, `agent_id=graphrag-chat`
3. Override back to `False` → chat works again

Against live Flagd, change the flag via Flagd’s API or by editing `flags.json` and restarting the `flagd` container.

## Opt-in Flagd smoke

From `app/infra`, with the API on demo auth. Do not point `FLAGD_URL` at a host that is not running: the API will fail closed.

```powershell
docker compose --profile flags up -d flagd
```

```powershell
$H = @{ Authorization = "Bearer compliance" }
# FLAGD_URL=http://127.0.0.1:8016 on the API process
Invoke-RestMethod -Method Post -Headers $H -ContentType "application/json" `
  -Uri http://127.0.0.1:8080/v1/chat `
  -Body '{"message":"gluten allergen policy","stream":false}'
# Expect 200, a request_id, and an audit row with flag_provider=flagd.
# Stop flagd and repeat: expect HTTP 503 and flag_provider=flagd_unavailable.
```

Record the HTTP status, `request_id`, and audit `model_route` / `flag_provider`. If Docker or Flagd is not running, mark this smoke **BLOCKED**. Do not claim a packet capture unless one was taken.

## Audit fields

Each chat audit entry may include `prompt_version`, `model_route`, `flag_variant`, `gateway`, `agent_id`, `team_id`.

## Tests

```powershell
cd app/backend
$env:OTEL_SDK_DISABLED="true"
.\.venv\Scripts\python.exe -m pytest -q tests/test_feature_flags.py
```
