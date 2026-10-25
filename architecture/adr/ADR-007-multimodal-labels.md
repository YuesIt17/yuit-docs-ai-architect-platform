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

Принимать **PDF, PNG, JPEG, WEBP, TIFF**. Пайплайн: MIME → rasterize PDF → **OCR provider=MOCK** extract → structured JSON → policy_check (GraphRAG). Raw + recognized в MinIO. CI — детерминированные fixtures.

**Реальный OCR** сложных сканов/чертежей — **вне текущего MVP** (known deviation; требует отдельного согласования). API/UI явно возвращают `ocr_provider=MOCK`. Не позиционировать mock как распознавание реального документа.

## Последствия

- (+) Демо контракта multimodal path; handoff через exports/outbox
- (−) Нет prod OCR accuracy; соответствие общей цели курса по OCR — риск до согласования

## Ссылки

- Sequence: [sequence-label.md](../sequence-label.md)
- ADR-009 (MinIO prefixes)
