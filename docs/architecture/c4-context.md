# C4 Level 1 — Контекст системы

**Схема (Draw.io):** [c4-context.png](../../diagrams/c4-context.png) · [c4-context.drawio](../../diagrams/c4-context.drawio)

## Назначение

Knowledge Platform RetailPartnerX встраивается в enterprise-ландшафт ритейлера: каналы магазинов и backoffice обращаются через BFF; платформа интегрируется с PIM, ERP, CDP/CRM и корпоративным IdP. Отдельно существует сервис рекомендаций (hw-2), границы с которым сохраняются через OpenAPI.

## Акторы и внешние системы

| Участник | Роль |
| -------- | ---- |
| Mobile/Web App, Store Tablet, Category Backoffice | Каналы пользователей |
| Backend BFF | Единая точка входа каналов; не знает ML-деталей |
| Knowledge Platform | GraphRAG, labels, ACL, on-prem LLM |
| AI Recsys Service | Персональные рекомендации (внешняя к KP) |
| PIM / ERP / CDP / IdP | Каталог, операции, профиль, аутентификация |

## Trust boundary

BFF вызывает Knowledge Platform только по OpenAPI (`/v1/chat`, `/v1/vision/label`). Внутренности LLM / графа / векторов каналам не экспонируются.

```mermaid
flowchart LR
  subgraph channels [Каналы_RetailPartnerX]
    App[Mobile_Web_App]
    Tablet[Store_Associate_Tablet]
    Backoffice[Category_Backoffice]
  end
  BFF[Backend_BFF]
  KP[Knowledge_Platform]
  Recsys[AI_Recsys_Service]
  PIM[PIM_Catalog]
  CDP[CDP_CRM]
  ERP[ERP]
  IdP[Corporate_IdP]

  App --> BFF
  Tablet --> BFF
  Backoffice --> BFF
  BFF --> KP
  BFF --> Recsys
  KP --> PIM
  KP --> ERP
  Recsys --> PIM
  BFF --> CDP
  BFF --> IdP
  KP --> IdP
```
