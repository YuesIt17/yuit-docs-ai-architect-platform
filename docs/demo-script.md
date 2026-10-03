# Demo Script (5–7 min)

1. **Bring-up** — `make demo` or `make api` with seeded memory store. Show `/health`, `/metrics`.
2. **ACL** — Chat as `manager` asking about secret promo margin → no 42% leak. Chat as `compliance` → secret policy available.
3. **GraphRAG** — Ask allergen policy question; show citations + `/v1/graph/stats`.
4. **Label** — `POST /v1/vision/label` with `datasets/fixtures/label.png.txt` as `label.png`; show allergens + MinIO URIs + outbox.
5. **Observability** — Jaeger UI `:16686`, Grafana `:3000`, Neo4j Browser `:7474` (compose).
6. **Close** — Control vs Data Plane slide from docs.