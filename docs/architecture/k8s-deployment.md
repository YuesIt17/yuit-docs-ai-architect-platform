# Kubernetes deployment (Docker Desktop + Helm)

## Топология

- **По умолчанию:** Docker Desktop Kubernetes (`kubectl` context `docker-desktop`)
- **Legacy:** kind-кластер `retailpartnerx-kp` через `$env:KP_K8S='kind'`
- **Helm chart** `infra/helm/knowledge-platform` (+ `values-desktop.yaml`)
- UI/API: http://kp.local:8088/ (ingress-nginx LoadBalancer; избегать :80 — IIS на Windows)
- Labels: `kp.retailpartnerx.io/plane=edge|control|data`

## LLM

| Режим | Как |
|------|-----|
| MOCK (default) | API в K8s; UI `/llm` показывает MOCK |
| OLLAMA | **Только Compose:** `make llm-ollama` → `qwen2.5:0.5b`; API в K8s: `host.docker.internal:11434/v1` — см. [SRE.md](../SRE.md) |
| VLLM | Compose profile `llm-gpu` (NVIDIA) |

Observability + S3 (compose): `make obs` → Grafana :3000, Prometheus :9090, MinIO :9000/:9001.

MinIO также включён в Desktop Helm (`STORE_BACKEND=live`) для объектов этикеток.

Frontend **никогда** не ходит в Ollama напрямую — только через API `/v1/chat` и `/v1/llm/*`.

## Подъём

```powershell
# prerequisites: Docker Desktop with Kubernetes enabled, helm, kubectl
.\scripts\k8s-up.ps1
# legacy kind:
# $env:KP_K8S = "kind"; .\scripts\k8s-up.ps1
```

Hosts: `127.0.0.1 kp.local`  
UI: http://kp.local:8088 · API: http://kp.local:8088/api/health

Снос: `.\scripts\k8s-down.ps1`

## Ops-команды

kubectl, curl, Helm, rollout — **[docs/SRE.md](../SRE.md)**.

## Docker Compose (без K8s)

```bash
make demo          # api + frontend + data plane + grafana/prometheus/minio
make obs           # prometheus + grafana + minio + jaeger only
make llm-ollama    # minimal ollama qwen2.5:0.5b (mem_limit 3g)
.\scripts\ollama-pull.ps1
make llm-vllm      # + vLLM (profile llm-gpu, needs NVIDIA)
```

UI: http://localhost:5173 · API: http://localhost:8080

## Smoke-чеклист

1. UI → pill LLM показывает provider
2. `/llm` → Apply MOCK → Chat с `model_uri=mock://...`
3. Роль `manager` → секретный promo → нет утечки `42%`
4. `/labels` upload `datasets/fixtures/label.png.txt` as `label.png`
5. `/ops` — health + audit
6. (Опционально) Ollama → Apply OLLAMA → Chat `llm_provider=OLLAMA`
