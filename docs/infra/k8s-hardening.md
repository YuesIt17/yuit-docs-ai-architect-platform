# Kubernetes Hardening

What the chart enforces, how it is verified, and what still needs a live cluster.

## Controls

| Control | Implementation |
| ------- | -------------- |
| Pod Security Standard | `restricted`, enforced by labels on the `kp` namespace |
| Non-root | Every pod sets a numeric `runAsUser`, `runAsNonRoot` and the `RuntimeDefault` seccomp profile, and drops all capabilities |
| Service account tokens | Not mounted, because no workload calls the Kubernetes API |
| Read-only root filesystem | `api`, `frontend`, `postgres`, `redis`, and `bff` and `keycloak` when enabled, with `emptyDir` volumes for writable paths |
| Network | Default-deny for ingress and egress, with allowlists per port |
| Secrets in manifests | The DSN and Neo4j credentials come from `kp-secrets` rather than plain pod env |
| Admission | Optional Kyverno policies in [`templates/kyverno.yaml`](../../app/infra/helm/knowledge-platform/templates/kyverno.yaml) |
| Authentication | Off by default. With `bff.enabled`, a distroless non-root BFF holds the tokens and the API validates each one: [ADR-010](../../architecture/adr/ADR-010-bff-auth.md) |

## Known exceptions

These pods keep a writable root filesystem. Each carries a `kp.retailpartnerx.io/writable-rootfs` label stating the reason, and the Kyverno policy rejects any other pod without a read-only root.

| Pod | Reason |
| --- | ------ |
| `neo4j` | The image entrypoint rewrites its config at startup |
| `qdrant` | Qdrant writes an init marker into its working directory |
| `minio` | The Bitnami entrypoint writes runtime config |

## Allowed traffic

| From | To | Ports |
| ---- | -- | ----- |
| ingress-nginx | frontend, api | 8080 |
| frontend | api | 8080 |
| api | postgres / neo4j / qdrant / redis / minio | 5432 / 7474, 7687 / 6333 / 6379 / 9000, 9001 |
| all pods | kube-dns | 53 |
| api (desktop overlay only) | host network: Ollama, vLLM, Tempo | 11434, 8000, 4318 |
| host network (desktop overlay only) | api, neo4j, minio console | 8080 / 7474, 7687 / 9001 |

## Real login mode

With `bff.enabled=true`, these rules replace the matching rows above:

| From | To | Ports |
| ---- | -- | ----- |
| ingress-nginx | frontend, bff, keycloak | 8080 |
| bff | api / redis / keycloak | 8080 / 6379 / 8080 |
| api | keycloak, for JWKS, in addition to the stores | 8080 |
| frontend | nothing beyond DNS: nginx only serves files | — |
| host network (desktop overlay only) | bff admin port, for metrics | 9090 |
| bff (desktop overlay only) | host network: Tempo | 4318 |

So in this mode:

- Only the BFF can reach the API. The ingress, the frontend and the host network no longer can, and the API's NodePort is removed even if an overlay asks for it.
- The Ingress routes `/api` and `/auth` to the BFF, and only `/idp/realms` and `/idp/resources` to Keycloak. The Keycloak admin console is not routed.
- The BFF's `/metrics` and probes are on a separate port that the Ingress never routes to, and its proxy allowlist keeps the API's `/metrics` and `/docs` internal.
- The realm import is a Secret, not a ConfigMap, because it holds the client secret and demo passwords. Neither the session key nor the client secret has a chart default outside the desktop overlay.
- Compose Prometheus cannot scrape the API, so its `kp-api-k8s` job shows as down. The BFF is scraped through NodePort 30091.

The bundled Keycloak is a demo. Its embedded database lives in an `emptyDir` and is re-imported at each start, so restarting it ends all sessions. For production, set `bff.oidc.issuerUrl` to an external IdP.

### Local development without TLS

`values-desktop-oidc.yaml` uses `http://kp.localhost:8088`. The BFF always sets a `Secure`, `__Host-` cookie, and browsers accept that on `*.localhost` because they treat it as a secure context. This was tested in Chromium only. The BFF refuses to start on any other plain-HTTP host, including `kp.local`.

## Admission policies

Kyverno needs its own install, so the policies are off by default:

```bash
helm repo add kyverno https://kyverno.github.io/kyverno/
helm install kyverno kyverno/kyverno -n kyverno --create-namespace --version 3.3.4
helm upgrade --install kp app/infra/helm/knowledge-platform -n kp -f app/infra/helm/knowledge-platform/values-desktop.yaml --set kyverno.enabled=true
```

## Verification

| Check | Status |
| ----- | ------ |
| Rendered manifests meet the controls (`pytest tests/architecture/test_chart_security.py`) | Automated |
| All pods start under Restricted with the new users and volumes | Verified on Docker Desktop, 2026-11-04: chat, ACL, label upload to MinIO and dialog history in PostgreSQL across an API restart |
| Real login mode: all pods start under Restricted with a read-only root, four roles log in, see only their documents and stream chat | Verified on Docker Desktop, 2026-11-05: [`oidc_e2e.py`](../../app/scripts/k8s/oidc_e2e.py), 99 checks |
| Policies block traffic, including "only the BFF reaches the API" | **Not run yet: requires a CNI that enforces them** |
| Kyverno rejects an unsafe pod | **Not run yet: requires Kyverno installed** |

The default Docker Desktop CNI accepts NetworkPolicy objects without enforcing them. To test enforcement, use kind with `disableDefaultCNI: true` and Calico.

## Upgrading an existing cluster

Docker Desktop's `hostpath` volumes ignore `fsGroup`, so files created by the earlier root containers stay unreadable by the new users. Qdrant is affected and crashes with `Permission denied`. To keep its data, follow the steps in [`migrate-qdrant-volume-owner.yaml`](../../app/infra/k8s/migrate-qdrant-volume-owner.yaml). PostgreSQL starts a new database in a `pgdata` subdirectory, which holds only dialog checkpoints.

A new install is not affected.

During a Qdrant rollout, the new pod can crash once with `Can't init WAL: WouldBlock` while the old pod still holds the volume. It recovers on its own after a restart.
