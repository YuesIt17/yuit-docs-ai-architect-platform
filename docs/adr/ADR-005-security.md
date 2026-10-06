# ADR-005: Security и RBAC

## Статус

Accepted

## Контекст

Критичный критерий: **User B не получает ответ по секретному документу**. Эволюция security layer из hw-6: PII, prompt injection, output guardrails + ACL на retrieval.

## Критерии выбора

- Фильтрация **до** LLM (не только post-hoc)
- Классификация документов и ролей
- Демо без полного IdP (учебный MVP)
- Защита vision-пути (MIME / size)

## Варианты

| Вариант | Плюсы | Минусы |
| ------- | ----- | ------ |
| ACL только в промпте | Просто | Легко обойти / утечки в citations |
| **ACL на chunk + output guard** | Defense in depth | Два места политики |
| Полный OIDC + ABAC | Prod-grade | Вне scope MVP |

## Решение

- Роли: `guest`, `store_associate`, `category_manager`, `compliance_officer`
- Классификации: `public` / `internal` / `secret` на Document/Chunk
- Retrieval **всегда** ACL-filtered; Output Guard блокирует утечку secret
- Vision: allowlist MIME + лимит размера
- Демо-токены в UI (не prod IdP); roadmap — корпоративный IdP

## Последствия

- (+) Демо manager vs compliance закрывает критерий курса
- (−) Demo bearer ≠ настоящая аутентификация; node-level Neo4j ACL — следующий этап

## Ссылки

- `backend/app/security/rbac.py`, `guardrails.py`
- Demo: [demo-script.md](../demo-script.md)
