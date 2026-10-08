# ADR-009: Object Store (MinIO / S3 API)

## Статус

Accepted

## Контекст

Нужно хранить сырые сканы, нормализованные растры, JSON распознавания и exports для PIM/ERP без складывания blobs в graph/SQL.

## Критерии выбора

- S3 API on-prem
- Разделение префиксов жизненного цикла объекта
- Presign / outbox для downstream
- URI-only в графе и БД

## Варианты

| Вариант | Плюсы | Минусы |
| ------- | ----- | ------ |
| **MinIO** | Self-hosted S3, compose-friendly | Ops дисков |
| Локальная ФС | Просто | Плохо для K8s / multi-node |
| Облачный S3 | Управляемость | Нарушает air-gap narrative |

## Решение

On-prem **MinIO** с префиксами `raw/`, `normalized/`, `recognized/`, `exports/`. Graph/DB хранят только URI. Downstream PIM/ERP — presigned GET + outbox-событие `label.recognized`.

## Последствия

- (+) Чистый handoff; соответствие data plane isolation
- (−) Нужна политика lifecycle / GC для demo volumes

## Ссылки

- Data Flow: [data-flow.md](../architecture/data-flow.md)
- MinIO in Helm (K8s) ports 9000/9001; Compose uses `STORE_BACKEND=memory`
