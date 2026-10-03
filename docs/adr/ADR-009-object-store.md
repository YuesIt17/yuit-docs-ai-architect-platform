# ADR-009: Object Store (MinIO / S3 API)

## Decision
On-prem **MinIO** with prefixes `raw/`, `normalized/`, `recognized/`, `exports/`.  
Graph/DB store URIs only. Downstream PIM/ERP via presigned GET + outbox `label.recognized`.