# ADR-008: Sync / Async и Semantic Cache

## Статус

Accepted

## Контекст

Интерактивный чат и распознавание этикетки требуют низкой latency (sync/SSE). Тяжёлые multi-hop / batch — async. Continuity hw-9: semantic cache снижает RPS на LLM.

## Критерии выбора

- Sync для UX чата
- Async для batch
- Инвалидация кэша при смене индекса
- Кэш только после Output Guard (не кэшировать утечки)

## Варианты

| Вариант | Плюсы | Минусы |
| ------- | ----- | ------ |
| Всё sync | Просто | Timeout на heavy |
| Всё async | Масштаб | Плохой UX чата |
| **Sync/SSE + async jobs + semantic cache** | Баланс | Два API-пути |

## Решение

- Sync/SSE для interactive chat и label extract
- Async `/v1/jobs` для batch / multi-hop
- Semantic cache **после** Output Guard; invalidate через `index_version` (hw-9)

## Последствия

- (+) Снижение OpEx LLM; сохранение UX
- (−) Риск stale cache при ошибке versioning

## Ссылки

- hw-9 high-load architecture
- Redis в Data Plane
