# Infrastructure and operations

Parent index: [docs/README.md](../README.md).

| Subfolder / doc | Purpose |
| --------------- | ------- |
| [sre/SRE.md](sre/SRE.md) | Runbook, ports, failure modes |
| [sec-ops/sec-ops.md](sec-ops/sec-ops.md) | DevSecOps lab (Trivy / Semgrep / …) |
| [k8s/](k8s/) | Architecture, primer, hardening |
| [compose/compose-dev.md](compose/compose-dev.md) | Hybrid Compose side-stack |
| [serving/vllm-profile.md](serving/vllm-profile.md) | Submission vLLM AWQ profile |
| [diagrams/DIAGRAMS.md](diagrams/DIAGRAMS.md) | Build / check architecture diagrams |
| [secrets.md](secrets.md) | Vault / ESO notes |

## When to use which path

| Path | When | Document | Diagram |
|------|-------|----------|-------|
| **Hybrid (recommended)** | Desktop demo | [compose/compose-dev.md](compose/compose-dev.md) + [k8s/k8s-architecture.md](k8s/k8s-architecture.md) | [k8s-topology-desktop.svg](../../architecture/diagrams/images/k8s-topology-desktop.svg) |
| **K8s + Helm primer** | Cluster objects, delivery | [k8s/k8s-primer.md](k8s/k8s-primer.md) | Mermaid in the document |
| **Hardening** | Restricted pods, NetworkPolicy, Kyverno | [k8s/k8s-hardening.md](k8s/k8s-hardening.md) | — |
| **DevSecOps lab** | `make sec-scan` | [sec-ops/sec-ops.md](sec-ops/sec-ops.md) | — |

## Zero-overlap (hybrid)

| Kubernetes `kp` | Compose `retailpartnerx-kp` |
|-----------------|-----------------------------|
| api, frontend | — |
| postgres, neo4j, qdrant, redis, **minio** | — |
| — | **ollama** (`make llm-ollama`) |
| — | prometheus, grafana, tempo, loki, alloy (`make obs`) |
| — | Trivy, Semgrep, … (ephemeral, `make sec-scan`) |

**Windows**

```powershell
.\app\scripts\hybrid\hybrid-up.ps1
# or: make demo

.\app\scripts\sec\sec-scan.ps1
# or: make sec-scan  → tmp/sec-ops/
```

**macOS**

```bash
bash app/scripts/hybrid/hybrid-up.sh
# or: make demo

bash app/scripts/sec/sec-scan.sh
# or: make sec-scan  → tmp/sec-ops/
```

## Startup

| What | Where |
|-----|-----|
| How-to (Win + Mac) | [SETUP.md](../getting-started/SETUP.md) |
| curl / kubectl / Helm | [SRE.md](sre/SRE.md) |
| Chart / compose code | [`app/infra/`](../../app/infra/) |
| Load captures | [../load-testing/](../load-testing/) |

Logical DMZ / Control / Data / GPU: [architecture/docs/deployment.md](../../architecture/docs/deployment.md).
