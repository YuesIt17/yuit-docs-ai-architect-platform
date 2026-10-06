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

- OpenTelemetry → Jaeger
- Prometheus: `llm_tokens_total`, `rag_latency_ms`, `vision_latency_ms`, `semantic_cache_hit_rate`
- Grafana datasource provisioned в compose profile `obs`
- Audit rows с FinOps-полем `cost_est`

## Последствия

- (+) Демо трейсов на защите; единый язык с SRE
- (−) Полнота spans зависит от покрытия кода; дашборды — starter

## Ссылки

- `backend/app/main.py`, `backend/app/services/metrics.py`
- Compose profile `obs`
