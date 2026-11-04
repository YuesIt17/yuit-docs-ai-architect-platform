#!/usr/bin/env bash
# Configure Vault for the platform. Expects VAULT_ADDR and VAULT_TOKEN to be set, and
# NEO4J_PASSWORD, MINIO_ROOT_USER, MINIO_ROOT_PASSWORD, POSTGRES_ADMIN_PASSWORD, JWT_SECRET
# to hold the values to store. Do not commit these values.
set -euo pipefail

: "${POSTGRES_HOST:=postgres.kp.svc.cluster.local}"
: "${POSTGRES_DB:=knowledge}"
: "${POSTGRES_ADMIN_USER:=kp}"

vault secrets enable -path=secret kv-v2 2>/dev/null || true
vault kv put secret/kp/platform \
  jwt_secret="$JWT_SECRET" \
  neo4j_password="$NEO4J_PASSWORD" \
  minio_root_user="$MINIO_ROOT_USER" \
  minio_root_password="$MINIO_ROOT_PASSWORD" \
  postgres_admin_password="$POSTGRES_ADMIN_PASSWORD"

vault secrets enable database 2>/dev/null || true
vault write database/config/kp-postgres \
  plugin_name=postgresql-database-plugin \
  allowed_roles=kp-api \
  connection_url="postgresql://{{username}}:{{password}}@${POSTGRES_HOST}:5432/${POSTGRES_DB}" \
  username="$POSTGRES_ADMIN_USER" \
  password="$POSTGRES_ADMIN_PASSWORD"

# Every generated user inherits one owner role. Without this, tables created by one
# short-lived user could not be read by the next, and rotation would lose dialog history.
PGPASSWORD="$POSTGRES_ADMIN_PASSWORD" psql -h "$POSTGRES_HOST" -U "$POSTGRES_ADMIN_USER" -d "$POSTGRES_DB" <<SQL
DO \$\$ BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'kp_app') THEN
    CREATE ROLE kp_app NOLOGIN;
  END IF;
END \$\$;
GRANT ALL ON SCHEMA public TO kp_app;
SQL

vault write database/roles/kp-api \
  db_name=kp-postgres \
  default_ttl=1h \
  max_ttl=24h \
  creation_statements="CREATE ROLE \"{{name}}\" LOGIN PASSWORD '{{password}}' VALID UNTIL '{{expiration}}' IN ROLE kp_app; ALTER ROLE \"{{name}}\" SET ROLE kp_app;"

vault policy write kp-eso - <<'POLICY'
path "secret/data/kp/*" { capabilities = ["read"] }
path "database/creds/kp-api" { capabilities = ["read"] }
POLICY

vault auth enable kubernetes 2>/dev/null || true
vault write auth/kubernetes/config kubernetes_host="https://kubernetes.default.svc"
vault write auth/kubernetes/role/kp-eso \
  bound_service_account_names=kp-vault-reader \
  bound_service_account_namespaces=kp \
  policies=kp-eso \
  ttl=1h

echo "Vault configured. Install with: --set secrets.provider=external-secrets"
