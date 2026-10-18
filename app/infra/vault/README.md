# Vault stub (file backend)

Production RetailPartnerX uses HashiCorp Vault / cloud secret manager.
For local MVP, secrets live in `.env` / compose env (never commit real credentials).

Planned paths:
- `secret/data/kp/neo4j`
- `secret/data/kp/minio`
- `secret/data/kp/jwt`
