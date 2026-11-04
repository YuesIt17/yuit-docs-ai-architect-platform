# ER / Data Model

**Diagram (intended DDL):** [er-conceptual.svg](../diagrams/images/er-conceptual.svg)

## Purpose

Storage of documents, chunks (vectors), labels, sessions, audit and outbox; RBAC through `classification` + `allowed_roles`.

## Entities

| Entity | Key fields |
| -------- | ------------- |
| Document | corpus, classification, allowed_roles, index_version |
| Chunk | embedding, modality, doc_id |
| LabelAsset | s3_uri_raw / recognized, classification |
| Session / ChatMessage | dialog history |
| AuditDecision | request_id, role, acl_decision, cost_est |
| Outbox | event_type (`label.recognized`), payload |

Graph ontology (nodes/edges): [ADR-003](adr/ADR-003-graph-db.md).

```mermaid
erDiagram
  DOCUMENT ||--o{ CHUNK : contains
  DOCUMENT ||--o{ ENTITY_LINK : about
  LABEL_ASSET ||--o| DOCUMENT : extracted_to
  SESSION ||--o{ CHAT_MESSAGE : has
  AUDIT_DECISION }o--|| SESSION : optional
  OUTBOX }o--|| LABEL_ASSET : emits

  DOCUMENT {
    string doc_id PK
    string corpus
    string classification
    string allowed_roles
    string index_version
  }
  CHUNK {
    string chunk_id PK
    string doc_id FK
    string modality
    vector embedding
  }
  LABEL_ASSET {
    uuid id PK
    string source_format
    string s3_uri_raw
    string s3_uri_recognized
    string classification
  }
  AUDIT_DECISION {
    bigint id PK
    string request_id
    string role
    string acl_decision
    float cost_est
  }
  OUTBOX {
    bigint id PK
    string event_type
    json payload
  }
```
