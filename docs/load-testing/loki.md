# Evidence: Loki Logs

## Capture session (2026-10-26, hybrid-up)

| Field | Value |
| ---- | -------- |
| Loki | Compose `:3100`, ready |
| Alloy | `retailpartnerx-kp-alloy-1` → Loki |
| Grafana | Explore → Loki |

## 1) Ollama logs in Loki (confirmed)

Query: `{job="retailpartnerx-kp-ollama-1"}`

Sample lines (2026-10-26):

```
[GIN] 2026/10/26 - 10:23:23 | 200 |      1.2738ms |    192.168.65.1 | GET      "/v1/models"
slot print_timing: id  0 | task 370 | n_gen =   2802, tg =   9.73 t/s, tg_3s =   7.80 t/s
```

## 2) API JSON logs + `trace_id` (kubectl; correlation with Tempo)

On Docker Desktop, Alloy more reliably scrapes **pause/`POD` sidecars** than the app container stream; the application's JSON with `trace_id` was verified through:

```powershell
kubectl -n kp logs -l app=api --tail=50 | Select-String trace_id
```

Sample lines (same session; `trace_id` matches Tempo):

```json
{"ts": "2026-10-26T10:17:46.793402+00:00", "service": "kp-api", "level": "info", "logger": "httpx", "msg": "HTTP Request: POST http://host.docker.internal:11434/v1/chat/completions \"HTTP/1.1 200 OK\"", "trace_id": "61c14b0a5bb0d7d6bbe71b21dbad12e8"}
{"ts": "2026-10-26T10:17:38.535435+00:00", "service": "kp-api", "level": "info", "logger": "httpx", "msg": "HTTP Request: GET http://host.docker.internal:11434/v1/models \"HTTP/1.1 200 OK\"", "trace_id": "f8fb0f847f19b3fd658a47521d5a131c"}
```

Chat evidence Trace ID in Tempo: `ca1a2261f25b8dbca04cae601bb671d1` (see [trace.md](trace.md)).

## Checklist

- [x] Loki receives Compose LLM logs (`retailpartnerx-kp-ollama-1`)
- [x] The API writes JSON with `trace_id` (kubectl)
- [x] Tempo has matching `kp-api` traces
- [ ] Ideal: Alloy labels the app container as `job=api` (follow-up; a quirk of Docker Desktop k8s scraping)

## Related

- Ops: `http://localhost:3000/explore` (Loki / Tempo)
- ADR-006 observability
