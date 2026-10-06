# ADR-007: Multimodal Label Recognition

## Статус

Accepted

## Контекст

RetailPartnerX обрабатывает сканы этикеток (PDF/PNG и др.): нужно извлечь структуру, связать с политиками через GraphRAG и отдать handoff в PIM/ERP.

## Критерии выбора

- Поддержка распространённых форматов этикеток
- Разделение raw / recognized / export в object store
- CI без тяжёлого OCR (fixtures / mock)
- Политический check после extract

## Варианты

| Вариант | Плюсы | Минусы |
| ------- | ----- | ------ |
| Только VLM end-to-end | Меньше пайплайна | Дорого по GPU, хуже audit |
| **Detect → rasterize → OCR/VLM → JSON → GraphRAG** | Контроль шагов | Больше компонентов |
| Ручная разметка | Качество | Не масштабируется |

## Решение

Принимать **PDF, PNG, JPEG, WEBP, TIFF**. Пайплайн: MIME → rasterize PDF → OCR/VLM extract → structured JSON → policy_check (GraphRAG). Raw + recognized в MinIO. CI — детерминированные fixtures / mock OCR; profile `vision` для реального OCR/VLM.

## Последствия

- (+) Демо multimodal path; handoff через exports/outbox
- (−) Качество OCR зависит от железа; mock ≠ prod accuracy

## Ссылки

- Sequence: [sequence-label.md](../architecture/sequence-label.md)
- ADR-009 (MinIO prefixes)
