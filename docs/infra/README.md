# Инфраструктура Knowledge Platform

| Путь | Когда | Документ | Схема |
|------|-------|----------|-------|
| **Hybrid (рекомендуется)** | Desktop демо / защита | [compose-dev.md](compose-dev.md) + [k8s-architecture.md](k8s-architecture.md) | [k8s-topology.png](../../diagrams/k8s-topology.png) |
| **Standalone Compose** | Без K8s / CI | [docker-compose.standalone.yml](../../infra/docker-compose.standalone.yml) | [compose-topology.png](../../diagrams/compose-topology.png) |
| **DevSecOps lab** | Аудит `kp` (Trivy / Semgrep / Nmap / ZAP / Nuclei / Checkov / kube-bench) | [sec-ops.md](sec-ops.md) | — |

## Zero-overlap (hybrid)

| Kubernetes `kp` | Compose `retailpartnerx-kp` |
|-----------------|-----------------------------|
| api, frontend | — |
| postgres, neo4j, qdrant, redis, **minio** | — |
| — | **ollama** (`make llm-ollama`) |
| — | prometheus, grafana, jaeger (`make obs`) |
| — | Trivy, Semgrep, Nmap, ZAP, Nuclei, kube-bench, Checkov (ephemeral, `make sec-scan`) |

**Windows**

```powershell
.\scripts\hybrid-up.ps1
# или: make demo

.\scripts\sec-scan.ps1
# или: make sec-scan  → tmp/sec-ops/
# глубокий (+ ZAP): $env:SEC_SCAN_DEEP = "1"; make sec-scan
```

**macOS**

```bash
bash scripts/hybrid-up.sh
# или: make demo

bash scripts/sec-scan.sh
# или: make sec-scan  → tmp/sec-ops/
# глубокий (+ ZAP): SEC_SCAN_DEEP=1 make sec-scan
```

## Запуск и ops

| Что | Где |
|-----|-----|
| How-to (Win + Mac) | [SETUP.md](../SETUP.md) |
| curl / kubectl / Helm | [SRE.md](../SRE.md) |
| DevSecOps / Security Engineer lab | [sec-ops.md](sec-ops.md) |
| Chart / compose | [`infra/`](../../infra/) |

Логические DMZ / Control / Data / GPU: [architecture/deployment.md](../architecture/deployment.md).
