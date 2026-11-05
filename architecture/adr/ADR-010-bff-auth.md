# ADR-010: Real Login with Keycloak and a Go BFF

## Status

Accepted. Optional in the chart and off by default. Verified on Docker Desktop on 2026-11-05, with the limits listed under [Not verified](#not-verified).

## Context

The UI sent a role name as the bearer token, and the API mapped it through `DEMO_USERS`. Anyone could claim any role, and unknown tokens became `guest`. Document ACL enforcement already worked, so this decision changes who the principal is, not the ACL logic.

The Python backend stays. The new code is one small service between the browser and FastAPI.

## Selection criteria

- Tokens never reach the browser, so an XSS bug cannot steal them
- The API validates every token itself and does not trust the service in front of it
- SSE chat streams pass through without buffering or timeouts
- Runs under Pod Security Restricted with a read-only root filesystem
- The memory cost fits a 4 GB Docker Desktop VM, or we say that it does not

## Options

| Option | Pros | Cons |
| ------ | ---- | ---- |
| Tokens in the SPA (public client) | No new service | Tokens are readable by any script on the page |
| **`oauth2-proxy`** | Maintained and widely deployed, supports OIDC and a Redis session store, and leaves us no auth code to own | One more config surface to learn, and login and logout behavior follow its model |
| **Custom BFF in Go** (chosen) | Exact control of the session, CSRF and logout contract, and it demonstrates the skill | We own security-sensitive code that a maintained project already provides |
| Custom BFF in Python | Same language as the backend | Adds another Python process and image on a small VM |

## Decision

A Go BFF in [`app/bff`](../../app/bff/README.md), with Keycloak as the identity provider.

### Why custom rather than `oauth2-proxy`

The honest answer: **`oauth2-proxy` would be a strong production choice, and for most teams the better one.** Writing this BFF does not mean `oauth2-proxy` falls short.

Two reasons drove the choice, and neither is that `oauth2-proxy` could not do the job:

1. **To demonstrate the skill.** This repository is a public portfolio. Building the flow shows how PKCE, session handling, CSRF and refresh rotation work together in a way that configuring a proxy does not.
2. **Streaming fit in Go.** `httputil.ReverseProxy` flushes per write, and a goroutine per open stream is cheap. Go produced a 27.6 MB distroless image and a 16 MiB process, measured below. Other languages could also do this. Go was a preference, not a requirement.

The custom contract has small benefits: `/auth/me` returns the role from the API together with a session-bound CSRF token, and logout ends the Keycloak session from the server with no confirmation page. These are conveniences. They would not justify owning this code in a team with no reason to learn it.

`oauth2-proxy` was not run or measured here, so this ADR makes no performance comparison. **Revisit this decision if the platform goes to production:** about 1,400 lines of auth code need security review and upkeep that a maintained proxy would remove.

Crypto and protocol work stays in libraries: `golang.org/x/oauth2`, `coreos/go-oidc`, and the standard library's `cipher.NewGCMWithRandomNonce` and `http.CrossOriginProtection`.

### How it works

```text
Browser ──__Host- cookie──▶ BFF ──bearer token──▶ API ──JWKS──▶ Keycloak
   │                         │ tokens, encrypted
   └──login form──▶ Keycloak └▶ Redis
```

| Concern | Implementation |
| ------- | -------------- |
| Login | Authorization Code with PKCE (S256) as a confidential client, plus `state` and `nonce`. A short-lived cookie binds `state` to the browser that started the login, and the login state can be redeemed once |
| Session | 130-bit opaque id in `__Host-kp_session`: `HttpOnly`, `Secure`, `SameSite=Lax`. Redis keys hold a SHA-256 of the id, and values are AES-256-GCM bound to their key. The TTL is an absolute 8 hours |
| CSRF | State-changing requests need both the standard library's cross-origin check and a token bound to the session |
| Refresh | Rotation, with `singleflight` inside a process and a Redis lock across replicas. `invalid_grant` ends the session, and an IdP outage does not |
| Logout | The server posts the refresh token to Keycloak's logout endpoint, so no ID token enters a browser URL |
| Proxy | Allowlist of `/api/health` and `/api/v1/*`, so `/metrics` and `/docs` stay internal. Replaces `Authorization`, strips cookies and the CSRF token, drops `Set-Cookie` from responses |
| Streaming | Flushes each write and clears the server's write deadline for proxied requests only |
| API | Validates signature, pinned RS256, issuer, audience and expiry on every request. `sub` becomes `user_id`. Invalid tokens get 401. A valid token with no platform role gets 403, never `guest` |
| Modes | The API refuses to start with both `DEMO_AUTH_ENABLED=true` and `OIDC_ISSUER`. With the BFF, the chart sets demo auth off whatever the values say |

### Plain-HTTP local development

There is no insecure cookie mode, because a flag that weakens the session cookie is a flag that can reach production.

The BFF always sets the strict cookie and refuses to start unless its public URL is HTTPS or `localhost`/`*.localhost`. Local development uses `http://kp.localhost:8088`. Browsers treat that host as a secure context, so the `__Host-` cookie works over plain HTTP.

This was tested in the Chromium-based browser pane of the Claude desktop app: both a throwaway test server and the full login flow kept the cookie. Other browsers, including Safari, were not tested. The old `kp.local` host cannot work with this cookie, so the BFF rejects it at startup rather than causing a silent login loop.

## Measurements

Docker Desktop on Windows, with a 3.8 GiB VM and no GPU. Raw output is in [`docs/evidence/bff-overhead.md`](../../docs/evidence/bff-overhead.md).

### Latency added by the BFF

Measured from a pod inside the cluster, comparing a direct API call with a bearer token against the same call through the BFF with a session cookie. Both include the API's JWT validation. Two runs:

| Scenario | Run 1 added | Run 2 added |
| -------- | ----------- | ----------- |
| `GET /v1/me`, one client, p50 | 1.85 ms | 1.50 ms |
| `GET /v1/me`, one client, p95 | 2.30 ms | -1.07 ms |
| `GET /v1/me`, 8 clients, p50 | 12.92 ms | -6.01 ms |
| `GET /v1/me`, 16 clients, p50 | 25.98 ms | 22.53 ms |
| Chat stream, time to first bytes, p50 (n=60) | 16.93 ms | 19.91 ms |
| Throughput at 16 clients | 149 → 114 req/s | 138 → 114 req/s |

How to read this:

- **About 2 ms per request on an idle system** is the most reliable number.
- **Under load the figures are noisy.** Negative values are measurement noise, not a speed-up. The load generator is a Python client on the same VM, and the API tops out near 140 req/s here. The 16-client throughput drop of about 20% is real for this setup, but it is not a capacity figure for the BFF alone.
- **The chat difference is small against a request of about 400 ms**, and p95 and p99 were dominated by outliers on both sides.

Each proxied request also costs a Redis read and an AES-GCM decryption, which is part of the numbers above.

### Memory

| Component | Measured |
| --------- | -------- |
| BFF | 13 to 16 MiB after load, limit 128 MiB |
| BFF image | 27.6 MB |
| Keycloak | 573 to 593 MiB, limit 768 MiB |
| Keycloak first start | 176 s on this VM, including the realm import |

### Does it fit in 4 GB?

**Yes, but with little margin.** With the platform, Keycloak and the BFF running and the observability stack stopped, `free -m` reported 1,473 MB available and 976 of 1,024 MB of swap in use.

With the full observability stack added, it reported 1,126 MB available with swap completely full. Other, unrelated containers were running during that reading. Everything kept working, but more load on this VM would risk memory pressure. Keycloak accounts for almost all of the added memory, and it is the part to replace with a shared instance outside the VM if this becomes a constraint.

## Consequences

- (+) No token reaches page scripts. In the real browser, `document.cookie` and web storage were empty after login
- (+) Each role logs in as a real user, and dialog threads are isolated by `sub`
- (+) Demo mode still works for tests and the MOCK profile
- (−) We own about 1,400 lines of security-sensitive Go, which is the main cost of this decision
- (−) Keycloak adds about 590 MiB, and login depends on it being up
- (−) In this mode the API has no NodePort, so Compose Prometheus cannot scrape it, and the `kp-api-k8s` job shows as down. The BFF's own metrics are scraped on port 30091
- (−) Keycloak shares the app's hostname here, under `/idp`, so its own login cookies reach the same host, scoped to its path. One is `KEYCLOAK_IDENTITY`, an HttpOnly signed JWT. It is not an API token, and the API answered 401 when it was presented as a bearer token. Production should give the IdP its own hostname
- (−) The API emits its SSE events together once the agent finishes, so users do not yet see token-by-token streaming. This predates the BFF, which forwards events as they arrive

## Verification

| Check | Result |
| ----- | ------ |
| Go tests with `-race`, `go vet`, `golangci-lint` | Pass, in a Linux container |
| Tests fail when protections are removed | Checked by temporarily removing them: write deadline clear, Redis lock, nonce check, state cookie check, header stripping, path allowlist, origin check |
| Python tests for valid, expired, wrong-audience, wrong-issuer, `alg=none`, HMAC confusion and unknown-role tokens | Pass |
| Each of the four roles logs in on Docker Desktop, sees only its documents and streams chat | Pass: [`oidc_e2e.py`](../../app/scripts/k8s/oidc_e2e.py) drives the real Keycloak form, with 99 checks and 0 failures |
| Login, chat and logout in a real browser | Pass, as `compliance` only. The other roles ran through the script |
| Logout ends the Keycloak session | Pass: the next login shows the password form |
| Refresh against real Keycloak | Pass: two waves of 30 concurrent requests near token expiry gave 60 × 200 and exactly 2 refreshes, the second using the rotated token |
| Traces | Pass: one trace spans `kp-bff`, `kp-api` and the agent's spans in Tempo |
| Metrics | Pass: Prometheus scrapes `kp-bff-k8s` |
| Logs | Pass: 4,000 live lines were all JSON, with no JWT, authorization code, `state` or refresh token |

### Not verified

- **NetworkPolicy enforcement.** Docker Desktop's CNI does not enforce it, so "only the BFF reaches the API" is checked on rendered manifests only
- **HTTPS.** The `__Host-` cookie was only exercised on `http://kp.localhost`
- **Browsers other than Chromium**
- **Several BFF replicas in a cluster.** The cross-replica lock is tested with two instances against an in-memory Redis, and the live run used one replica
- **Keycloak's reuse detection.** The realm enables it, but only the fake IdP in the Go tests exercised reuse
- **BFF logs in Loki.** Alloy does not ship Docker Desktop Kubernetes pod logs, which is the existing gap in [`docs/evidence/loki.md`](../../docs/evidence/loki.md)
- **Flushing with a real LLM.** Immediate flush is proven by a Go test, and the live runs used the MOCK provider
- **An external IdP, Vault-backed BFF secrets and Kyverno with the new pods.** These are rendered and tested as manifests, not run
- **The `bff` CI workflow on GitHub.** Its steps were run locally
- **`KP_AUTH=oidc` in the `k8s-up` scripts.** They were only syntax-checked. The images and the `helm upgrade` were run by hand, because the scripts also upgrade `ingress-nginx`

## References

- [`app/bff`](../../app/bff/README.md), `app/backend/kp/security/rbac.py`
- [`docs/infra/k8s-hardening.md`](../../docs/infra/k8s-hardening.md)
- Supersedes the "demo tokens" decision in [ADR-005](ADR-005-security.md) when the BFF is enabled
