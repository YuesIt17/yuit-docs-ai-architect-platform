# Evidence: Tempo Traces

## Capture session (2026-10-26, hybrid-up)

| Field | Value |
| ---- | -------- |
| Stack | K8s API (ns `kp`) + Compose Tempo `:3200` / OTLP `:4318` |
| LLM | Ollama `qwen2.5:0.5b` through `host.docker.internal:11434` |
| **Trace ID** | `ca1a2261f25b8dbca04cae601bb671d1` |
| Root span | `POST /v1/chat` |
| Grafana | Explore → Tempo → paste the Trace ID |
| API | `http://127.0.0.1:3200/api/traces/ca1a2261f25b8dbca04cae601bb671d1` |

## Observed spans (this trace)

| Span |
| ---- |
| `POST /v1/chat` (FastAPI / OTel instrumentation) |
| `cache` |
| `input_guard` |
| `graph_retrieve` |
| `vector_retrieve` |
| `rerank` |
| `output_guard` |

> Note: the `llm` span may be absent on short or failed synthesize paths; other chat traces also appear under the `kp-api` service in Tempo search. Domain span names come from `kp/observability/spans.py` + the agent graph.

## How to update

```powershell
# After one chat in the UI:
curl.exe -s "http://127.0.0.1:3200/api/search?limit=20"
# Pick a trace with rootTraceName POST /v1/chat, then:
curl.exe -s "http://127.0.0.1:3200/api/traces/<TRACE_ID>"
```

Or Grafana Explore → Tempo → Search `service.name=kp-api`.
