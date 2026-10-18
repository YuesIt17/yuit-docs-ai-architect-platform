# ADR-006: Observability

## Статус

Accepted

## Контекст

Для защиты и ops нужны трейсы «под капотом» (Jaeger/OTel), метрики токенов и latency (Prometheus/Grafana), audit решений для FinOps (связь с hw-10).

## Критерии выбора

- OpenTelemetry tracing end-to-end запроса
- Метрики LLM / RAG / vision
- Self-hosted стек в compose
- Не тянуть SaaS-only (Langfuse cloud опционален)

## Варианты

| Вариант | Плюсы | Минусы |
| ------- | ----- | ------ |
| **OTel → Jaeger + Prom/Grafana** | Стандарт, air-gap | Нужна дисциплина instrumentation |
| Langfuse self-host | Удобные LLM traces | Ещё один сервис |
| Только логи | Просто | Слабо для защиты |

## Решение

- OpenTelemetry → Jaeger (`FastAPIInstrumentor.instrument_app`, OTLP/HTTP `:4318/v1/traces`)
- Prometheus: `llm_tokens_total`, `rag_latency_ms`, `vision_latency_ms`, `semantic_cache_hit_rate`, `kp_requests_total`, `acl_denies_total`
- Grafana: datasource + provisioned dashboard **KP Overview** (`app/infra/grafana/provisioning/`)
- Hybrid scrape: `host.docker.internal:30080/metrics` (API NodePort)
- Audit rows с FinOps-полем `cost_est`

## Последствия

- (+) Демо трейсов на защите; единый язык с SRE
- (−) Полнота spans зависит от покрытия кода; дашборды — starter

## Ссылки

- `app/backend/app/main.py`, `app/backend/app/services/metrics.py`
- Compose profile `obs`
