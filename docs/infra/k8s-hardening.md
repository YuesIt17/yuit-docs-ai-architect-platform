# Kubernetes Hardening

What the chart enforces, how it is verified, and what still needs a live cluster.

## Controls

| Control | Implementation |
| ------- | -------------- |
| Pod Security Standard | `restricted`, enforced by labels on the `kp` namespace |
| Non-root | Every pod sets a numeric `runAsUser`, `runAsNonRoot` and the `RuntimeDefault` seccomp profile, and drops all capabilities |
| Service account tokens | Not mounted, because no workload calls the Kubernetes API |
| Read-only root filesystem | `api`, `frontend`, `postgres`, `redis`, with `emptyDir` volumes for writable paths |
| Network | Default-deny for ingress and egress, with allowlists per port |
| Secrets in manifests | The DSN and Neo4j credentials come from `kp-secrets` rather than plain pod env |
| Admission | Optional Kyverno policies in [`templates/kyverno.yaml`](../../app/infra/helm/knowledge-platform/templates/kyverno.yaml) |

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
| All pods start under Restricted with the new users and volumes | **Not run yet: requires a live cluster** |
| Policies block traffic | **Not run yet: requires a CNI that enforces them** |
| Kyverno rejects an unsafe pod | **Not run yet: requires Kyverno installed** |

The default Docker Desktop CNI accepts NetworkPolicy objects without enforcing them. To test enforcement, use kind with `disableDefaultCNI: true` and Calico.

After upgrading an existing cluster, recreate the data volumes with `k8s-down` first. Files created by the earlier root containers may not be readable by the new users.
