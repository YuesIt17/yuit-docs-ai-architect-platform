# Vault setup

[`bootstrap.sh`](bootstrap.sh) configures KV storage, dynamic PostgreSQL credentials and Kubernetes auth for External Secrets Operator. See [docs/infra/secrets.md](../../../docs/infra/secrets.md).

The local demo does not need Vault: its secrets come from chart values or `.env`. Never commit real credentials.
