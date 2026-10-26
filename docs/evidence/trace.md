# Evidence: трассы Tempo

## Сессия захвата (2026-10-26, hybrid-up)

| Поле | Значение |
| ---- | -------- |
| Стек | K8s API (ns `kp`) + Compose Tempo `:3200` / OTLP `:4318` |
| LLM | Ollama `qwen2.5:0.5b` через `host.docker.internal:11434` |
| **Trace ID** | `ca1a2261f25b8dbca04cae601bb671d1` |
| Корневой span | `POST /v1/chat` |
| Grafana | Explore → Tempo → вставить Trace ID |
| API | `http://127.0.0.1:3200/api/traces/ca1a2261f25b8dbca04cae601bb671d1` |

## Наблюдаемые span (эта трасса)

| Span |
| ---- |
| `POST /v1/chat` (FastAPI / OTel instrumentation) |
| `cache` |
| `input_guard` |
| `graph_retrieve` |
| `vector_retrieve` |
| `rerank` |
| `output_guard` |

> Примечание: span `llm` может отсутствовать на коротких/упавших путях synthesize; другие chat-трассы тоже есть под сервисом `kp-api` в поиске Tempo. Имена доменных span — из `kp/observability/spans.py` + agent graph.

## Как обновить

```powershell
# После одного chat в UI:
curl.exe -s "http://127.0.0.1:3200/api/search?limit=20"
# Выбрать трассу с rootTraceName POST /v1/chat, затем:
curl.exe -s "http://127.0.0.1:3200/api/traces/<TRACE_ID>"
```

Или Grafana Explore → Tempo → Search `service.name=kp-api`.
