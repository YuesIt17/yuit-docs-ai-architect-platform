# Data Flow

**Diagram:** [data-flow.svg](../diagrams/images/data-flow.svg)

> A mandatory artifact under the course criteria (a missing Data Flow is grounds for rejection).

## Text ingest (policies / KB)

Seed JSON (including a Russian law sample) → chunk → embed → Vector Index; in parallel, nodes/edges go to Neo4j (and the in-memory mirror for the MVP runtime).

```mermaid
flowchart LR
  Seed[Seed_JSON] --> Chunk[Chunk]
  Chunk --> Embed[Embed]
  Embed --> Vec[Vector_Index]
  Chunk --> Graph[Neo4j_Nodes_Edges]
```

## Label ingest + handoff

Upload PDF/PNG → MinIO `raw/` → normalize/rasterize → OCR extract → `recognized/` + `exports/` → Graph + Vectors → PIM/ERP through presign / outbox `label.recognized`.

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

## Chat query path (summary)

Request → Input Guard → (Semantic Cache) → Graph resolve → Vector+ACL → LLM → Output Guard → Audit → SSE/JSON.

See [sequence-chat.md](sequence-chat.md).
