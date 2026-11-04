# Secrets

The chart supports two sources for `kp-secrets`, selected by `secrets.provider`.

| Provider | Source | Use |
| -------- | ------ | --- |
| `helm` (default) | Chart values | Local demo with throwaway passwords |
| `external-secrets` | HashiCorp Vault through External Secrets Operator | Any shared environment |

## Vault setup

```bash
helm repo add external-secrets https://charts.external-secrets.io
helm install external-secrets external-secrets/external-secrets -n external-secrets --create-namespace
```

Set `VAULT_ADDR`, `VAULT_TOKEN` and the values to store, then run [`app/infra/vault/bootstrap.sh`](../../app/infra/vault/bootstrap.sh). Install the platform with `--set secrets.provider=external-secrets`.

## Rotation

| Secret | Mechanism | How the app picks it up |
| ------ | --------- | ----------------------- |
| PostgreSQL | Vault issues a dynamic user with a 1 h TTL, and ESO refreshes it every 30 min | No restart: the DSN is mounted as a file, and new connections read it |
| Neo4j, MinIO, JWT | Vault KV | Restart the API after changing them |

Dynamic PostgreSQL rotation works as follows:

1. ESO writes new credentials into the `kp-postgres-dsn` Secret, and the kubelet updates the mounted file.
2. The connection pool reads `POSTGRES_DSN_FILE` each time it opens a connection, and `SESSION_POOL_MAX_LIFETIME` (30 min) retires old connections before the lease ends.
3. All generated users inherit the `kp_app` role, which owns the tables, so a new user can read the dialog history that the previous one wrote.

## Limits

- **Not run yet:** the rendered manifests are checked by tests, and DSN file re-reading is unit tested. The full flow needs a live cluster with Vault and ESO.
- `bootstrap.sh` is written for a first setup. Review it before running it against a Vault that holds other data.
- The Vault token in the setup step is an operator credential, so use a short-lived one.
