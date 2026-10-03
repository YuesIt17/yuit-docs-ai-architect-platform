# C4 Level 1 — System Context

RetailPartnerX Knowledge Platform sits inside the retail enterprise landscape.

```mermaid
flowchart LR
  subgraph channels [RetailPartnerX_Channels]
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

**Trust boundary:** BFF calls Knowledge Platform via OpenAPI only (`/v1/chat`, `/v1/vision/label`). ML internals are not exposed to channels.