# Нагрузочный отчёт (smoke)

> Учебный smoke на локальном железе с **MOCK LLM**. Это **не** production SLO и не замена нагрузочного стенда с vLLM на GPU.

## Методика

| Параметр | Значение |
| -------- | -------- |
| Сценарий | GraphRAG chat path (in-process), ACL включён |
| Клиент | локальный smoke / HTTP к API |
| LLM | MOCK (нулевая генерация) |
| Запросов | 20 |
| Цель замера | оценить потолок API+RAG без GPU |

## Результаты

| Метрика | Значение | Железо / условия |
| ------- | -------- | ---------------- |
| RPS | ~130.8 | local MOCK LLM |
| Latency avg | ~7.6 ms | |
| Latency p95 | ~10.8 ms | |
| LLM provider | MOCK | |
| Requests | 20 | GraphRAG in-process |

## Сценарии (дизайн)

| Сценарий | Что измеряем | Комментарий |
| -------- | ------------ | ----------- |
| Chat FAQ (MOCK) | RPS / p95 API+RAG | таблица выше |
| Chat + ACL deny | корректность фильтра | функциональный критерий, не RPS |
| Label mock OCR | p95 vision path | цель дизайна &lt; 1 s (см. capability matrix) |
| Chat + Ollama/vLLM | tokens/s, p95 E2E | требует GPU; для видео на аренде |

## Вывод

На MOCK система держит порядка **~130 RPS** при p95 **~11 ms** на описанном smoke. Узкое место продакшена — LLM Serving (см. hw-7 sizing и ADR-001), а не слой GraphRAG ACL. Для отчёта на защите с реальной моделью — повторить замер на Yandex DataSphere / Cloud.ru GPU на 1–2 часа.
