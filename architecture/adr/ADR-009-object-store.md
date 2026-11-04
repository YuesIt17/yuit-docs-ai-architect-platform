# ADR-009: Object Store (MinIO / S3 API)

## Status

Accepted

## Context

The platform must store raw scans, normalized rasters, recognition JSON and PIM/ERP exports without putting blobs into the graph or SQL.

## Selection criteria

- On-prem S3 API
- Separate prefixes for the object lifecycle
- Presign / outbox for downstream systems
- URI-only references in the graph and DB

## Options

| Option | Pros | Cons |
| ------ | ---- | ---- |
| **MinIO** | Self-hosted S3, Compose-friendly | Disk operations |
| Local filesystem | Simple | Poor fit for K8s / multi-node |
| Cloud S3 | Managed | Breaks the air-gap narrative |

## Decision

On-prem **MinIO** with `raw/`, `normalized/`, `recognized/`, `exports/` prefixes. The graph and DB store URIs only. Downstream PIM/ERP use a presigned GET and a `label.recognized` outbox event.

## Consequences

- (+) Clean handoff; matches data plane isolation
- (−) Needs a lifecycle / GC policy for demo volumes

## References

- Data Flow: [data-flow.md](../docs/data-flow.md)
- MinIO in Helm (K8s) ports 9000/9001; Compose uses `STORE_BACKEND=memory`
