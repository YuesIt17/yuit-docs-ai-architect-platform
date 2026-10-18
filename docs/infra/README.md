# Инфраструктура Knowledge Platform

| Путь | Когда | Документ | Схема |
|------|-------|----------|-------|
| **Hybrid (рекомендуется)** | Desktop демо / защита | [compose-dev.md](compose-dev.md) + [k8s-architecture.md](k8s-architecture.md) | [k8s-topology.png](../../architecture/diagrams/k8s-topology.png) |
| **K8s + Helm primer** | Сущности кластера, схема связей, поставка фич | [k8s-primer.md](k8s-primer.md) | mermaid в документе |
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
.\app\scripts\hybrid\hybrid-up.ps1
# или: make demo

.\app\scripts\sec\sec-scan.ps1
# или: make sec-scan  → tmp/sec-ops/
# глубокий (+ ZAP): $env:SEC_SCAN_DEEP = "1"; make sec-scan
```

**macOS**

```bash
bash app/scripts/hybrid/hybrid-up.sh
# или: make demo

bash app/scripts/sec/sec-scan.sh
# или: make sec-scan  → tmp/sec-ops/
# глубокий (+ ZAP): SEC_SCAN_DEEP=1 make sec-scan
```

## Запуск и ops

| Что | Где |
|-----|-----|
| How-to (Win + Mac) | [SETUP.md](../SETUP.md) |
| curl / kubectl / Helm | [SRE.md](../SRE.md) |
| Сущности K8s / Helm / поставка | [k8s-primer.md](k8s-primer.md) |
| DevSecOps / Security Engineer lab | [sec-ops.md](sec-ops.md) |
| Chart / compose | [`app/infra/`](../../app/infra/) |

Логические DMZ / Control / Data / GPU: [architecture/deployment.md](../../architecture/deployment.md).
