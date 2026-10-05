# Kubernetes deployment (Docker Desktop + Helm)

## Topology

- **Default:** Docker Desktop Kubernetes (`kubectl` context `docker-desktop`)
- **Legacy:** kind cluster `retailpartnerx-kp` via `$env:KP_K8S='kind'`
- **Helm chart** `infra/helm/knowledge-platform` (+ `values-desktop.yaml`)
- UI/API: http://kp.local:8088/ (ingress-nginx LoadBalancer; avoid :80 — IIS on Windows)
- Labels: `kp.retailpartnerx.io/plane=edge|control|data`

## LLM

| Mode | How |
|------|-----|
| MOCK (default) | API in K8s; UI `/llm` shows MOCK |
| OLLAMA | **Compose only:** `make llm-ollama` → `qwen2.5:0.5b`; API в K8s: `host.docker.internal:11434/v1` — см. [SRE.md](../SRE.md) |
| VLLM | Compose profile `llm-gpu` (NVIDIA) |

Observability + S3 (compose): `make obs` → Grafana :3000, Prometheus :9090, MinIO :9000/:9001.

MinIO also enabled in Desktop Helm (`STORE_BACKEND=live`) for label objects.

Frontend never talks to Ollama directly — only via API `/v1/chat` and `/v1/llm/*`.

## Bring-up

```powershell
# prerequisites: Docker Desktop with Kubernetes enabled, helm, kubectl
.\scripts\k8s-up.ps1
# legacy kind:
# $env:KP_K8S = "kind"; .\scripts\k8s-up.ps1
```

Hosts file: `127.0.0.1 kp.local`  
UI: http://kp.local:8088 · API: http://kp.local:8088/api/health

Teardown: `.\scripts\k8s-down.ps1`

## Ops commands

kubectl, curl, Helm, rollout — **[docs/SRE.md](../SRE.md)**.

## Docker Compose (local without K8s)

```bash
make demo          # api + frontend + data plane + grafana/prometheus/minio
make obs           # prometheus + grafana + minio + jaeger only
make llm-ollama    # minimal ollama qwen2.5:0.5b (mem_limit 3g)
.\scripts\ollama-pull.ps1
make llm-vllm      # + vLLM (profile llm-gpu, needs NVIDIA)
```

UI: http://localhost:5173 · API: http://localhost:8080

## Smoke checklist

1. Open UI → header LLM pill shows provider
2. `/llm` → Apply MOCK → Chat works with `model_uri=mock://...`
3. Role `manager` → secret promo prompt → no `42%` leak
4. `/labels` upload `datasets/fixtures/label.png.txt` as `label.png`
5. `/ops` shows health + audit
6. (Optional) Ollama up → Apply OLLAMA → Chat `llm_provider=OLLAMA`
