# Knowledge Platform Infrastructure

| Path | When | Document | Diagram |
|------|-------|----------|-------|
| **Hybrid (recommended)** | Desktop demo | [compose-dev.md](compose-dev.md) + [k8s-architecture.md](k8s-architecture.md) | [k8s-topology-desktop.svg](../../architecture/diagrams/images/k8s-topology-desktop.svg) |
| **K8s + Helm primer** | Cluster objects, relationship map, feature delivery | [k8s-primer.md](k8s-primer.md) | Mermaid in the document |
| **Hardening** | Restricted pods, default-deny network, Kyverno admission | [k8s-hardening.md](k8s-hardening.md) | — |
| **DevSecOps lab** | `kp` audit (Trivy / Semgrep / Nmap / ZAP / Nuclei / Checkov / kube-bench) | [sec-ops.md](sec-ops.md) | — |

## Zero-overlap (hybrid)

| Kubernetes `kp` | Compose `retailpartnerx-kp` |
|-----------------|-----------------------------|
| api, frontend | — |
| postgres, neo4j, qdrant, redis, **minio** | — |
| — | **ollama** (`make llm-ollama`) |
| — | prometheus, grafana, tempo, loki, alloy (`make obs`) |
| — | Trivy, Semgrep, Nmap, ZAP, Nuclei, kube-bench, Checkov (ephemeral, `make sec-scan`) |

**Windows**

```powershell
.\app\scripts\hybrid\hybrid-up.ps1
# or: make demo

.\app\scripts\sec\sec-scan.ps1
# or: make sec-scan  → tmp/sec-ops/
# deep (+ ZAP): $env:SEC_SCAN_DEEP = "1"; make sec-scan
```

**macOS**

```bash
bash app/scripts/hybrid/hybrid-up.sh
# or: make demo

bash app/scripts/sec/sec-scan.sh
# or: make sec-scan  → tmp/sec-ops/
# deep (+ ZAP): SEC_SCAN_DEEP=1 make sec-scan
```

## Startup and ops

| What | Where |
|-----|-----|
| How-to (Win + Mac) | [SETUP.md](../SETUP.md) |
| curl / kubectl / Helm | [SRE.md](../SRE.md) |
| K8s objects / Helm / delivery | [k8s-primer.md](k8s-primer.md) |
| DevSecOps / Security Engineer lab | [sec-ops.md](sec-ops.md) |
| Chart / compose | [`app/infra/`](../../app/infra/) |

Logical DMZ / Control / Data / GPU: [architecture/docs/deployment.md](../../architecture/docs/deployment.md).
