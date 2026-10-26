# Evidence: логи Loki

## Сессия захвата (2026-10-26, hybrid-up)

| Поле | Значение |
| ---- | -------- |
| Loki | Compose `:3100`, ready |
| Alloy | `retailpartnerx-kp-alloy-1` → Loki |
| Grafana | Explore → Loki |

## 1) Логи Ollama в Loki (подтверждено)

Запрос: `{job="retailpartnerx-kp-ollama-1"}`

Примеры строк (2026-10-26):

```
[GIN] 2026/10/26 - 10:23:23 | 200 |      1.2738ms |    192.168.65.1 | GET      "/v1/models"
slot print_timing: id  0 | task 370 | n_gen =   2802, tg =   9.73 t/s, tg_3s =   7.80 t/s
```

## 2) JSON-логи API + `trace_id` (kubectl; корреляция с Tempo)

На Docker Desktop Alloy чаще надёжно скрейпит **pause/`POD` sidecars**, а не поток app-контейнера; JSON приложения с `trace_id` проверен через:

```powershell
kubectl -n kp logs -l app=api --tail=50 | Select-String trace_id
```

Примеры строк (та же сессия; `trace_id` совпадает с Tempo):

```json
{"ts": "2026-10-26T10:17:46.793402+00:00", "service": "kp-api", "level": "info", "logger": "httpx", "msg": "HTTP Request: POST http://host.docker.internal:11434/v1/chat/completions \"HTTP/1.1 200 OK\"", "trace_id": "61c14b0a5bb0d7d6bbe71b21dbad12e8"}
{"ts": "2026-10-26T10:17:38.535435+00:00", "service": "kp-api", "level": "info", "logger": "httpx", "msg": "HTTP Request: GET http://host.docker.internal:11434/v1/models \"HTTP/1.1 200 OK\"", "trace_id": "f8fb0f847f19b3fd658a47521d5a131c"}
```

Trace ID chat-evidence в Tempo: `ca1a2261f25b8dbca04cae601bb671d1` (см. [trace.md](trace.md)).

## Чеклист

- [x] Loki принимает логи Compose LLM (`retailpartnerx-kp-ollama-1`)
- [x] API пишет JSON с `trace_id` (kubectl)
- [x] В Tempo есть matching-трассы `kp-api`
- [ ] Идеал: Alloy помечает app-контейнер как `job=api` (follow-up — особенность scrape Docker Desktop k8s)

## Связанное

- Ops: `http://localhost:3000/explore` (Loki / Tempo)
- ADR-006 observability
