# Data Flow — потоки данных

**Схема (Draw.io):** [data-flow.png](../../diagrams/data-flow.png) · [data-flow.drawio](../../diagrams/data-flow.drawio)

> Обязательный артефакт по критериям курса (анти-reject: «нет Data Flow»).

## Text ingest (политики / KB)

Seed JSON (в т.ч. RU law sample) → chunk → embed → Vector Index; параллельно узлы/рёбра в Neo4j (и in-memory mirror для MVP runtime).

```mermaid
flowchart LR
  Seed[Seed_JSON] --> Chunk[Chunk]
  Chunk --> Embed[Embed]
  Embed --> Vec[Vector_Index]
  Chunk --> Graph[Neo4j_Nodes_Edges]
```

## Label ingest + handoff

Upload PDF/PNG → MinIO `raw/` → normalize/rasterize → OCR extract → `recognized/` + `exports/` → Graph + Vectors → PIM/ERP через presign / outbox `label.recognized`.

```mermaid
flowchart LR
  Upload[PDF_PNG_Upload] --> Raw[MinIO_raw]
  Raw --> Norm[Normalize_Rasterize]
  Norm --> Rec[OCR_Extract]
  Rec --> RecS3[MinIO_recognized]
  Rec --> Exp[MinIO_exports]
  Rec --> Graph[Graph_plus_Vectors]
  Exp --> PIM[PIM_ERP_via_presign_or_outbox]
```

## Chat query path (кратко)

Request → Input Guard → (Semantic Cache) → Graph resolve → Vector+ACL → LLM → Output Guard → Audit → SSE/JSON.

См. [sequence-chat.md](sequence-chat.md).
