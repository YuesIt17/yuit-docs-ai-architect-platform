# BFF

A backend-for-frontend between the browser, Keycloak and the API. It holds the tokens, so the browser only ever has an opaque session cookie. For the reasoning and the measurements, see [ADR-010](../../architecture/adr/ADR-010-bff-auth.md).

## Routes

| Route | Purpose |
| ----- | ------- |
| `GET /auth/login` | Starts Authorization Code with PKCE. Takes an optional same-origin `return_to` |
| `GET /auth/callback` | Finishes the login and sets the cookie |
| `GET /auth/me` | User, role, clearance and CSRF token, or 401 |
| `POST /auth/logout` | Ends this session and the Keycloak session. Needs the CSRF token |
| `GET /api/v1/auth/mode` | Proxied without a session, so the UI can decide what to show |
| `/api/health`, `/api/v1/*` | Proxied to the API with the bearer token. Needs a session, and a CSRF token if state-changing |

The admin port (9090) serves `/healthz`, `/readyz` and `/metrics`. The ingress never routes to it.

## Configuration

| Variable | Required | Purpose |
| -------- | -------- | ------- |
| `BFF_PUBLIC_URL` | Yes | The origin the browser uses: HTTPS, or HTTP on `*.localhost` |
| `OIDC_ISSUER_URL` | Yes | The issuer in tokens |
| `OIDC_DISCOVERY_URL` | No | An internal URL for discovery, when the issuer does not resolve in the cluster |
| `OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET` | Yes | The confidential client |
| `SESSION_ENCRYPTION_KEY` | Yes | 32 bytes in base64: `openssl rand -base64 32`. Changing it signs everyone out |
| `SESSION_TTL` | No | Absolute session lifetime. Default `8h` |
| `API_UPSTREAM_URL` | No | Default `http://api:8080` |
| `REDIS_URL` | No | Default `redis://redis:6379/1` |
| `BFF_LISTEN_ADDR`, `BFF_ADMIN_ADDR` | No | Default `:8080`, `:9090` |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | No | Tempo. `OTEL_SDK_DISABLED=true` turns tracing off |

## Commands

The race detector needs cgo, so on Windows run the tests in a Linux container:

```bash
docker run --rm -v "$PWD":/src -w /src golang:1.26 sh -c "go vet ./... && go test -race -count=1 ./..."
```

```bash
docker run --rm -v "$PWD":/src -w /src golangci/golangci-lint:v2.15.0 golangci-lint run ./...
```

Run on Docker Desktop, from the repository root:

```bash
KP_AUTH=oidc bash app/scripts/k8s/k8s-up.sh
```

```bash
python app/scripts/k8s/oidc_e2e.py
```

Then open <http://kp.localhost:8088/>. The demo users are in [`values-desktop-oidc.yaml`](../infra/helm/knowledge-platform/values-desktop-oidc.yaml).

## Layout

| Package | Purpose |
| ------- | ------- |
| `cmd/bff` | Wiring and shutdown |
| `internal/auth` | Login, callback, logout, `/auth/me`, CSRF and refresh |
| `internal/session` | Encrypted Redis store and the refresh lock |
| `internal/proxy` | Reverse proxy and path allowlist |
| `internal/obs` | JSON logs, Prometheus metrics, OpenTelemetry |
| `internal/server` | Routes, listeners and timeouts, plus the end-to-end tests |
| `internal/testidp` | An OIDC provider for tests |
