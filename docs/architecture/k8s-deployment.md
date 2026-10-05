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
| MOCK (default) | API only; UI `/llm` shows MOCK |
| OLLAMA | Compose: `.\scripts\ollama-pull.ps1` then UI Apply; or `KP_LLM=ollama` + k8s-up |
| VLLM | Compose profile `llm-gpu` (not default on kind) |

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

## Useful kubectl

```powershell
kubectl config use-context docker-desktop
kubectl -n kp get pods
kubectl -n kp get pods -o wide
kubectl -n kp get all,ingress
kubectl -n kp describe pod <name>
kubectl -n kp logs deploy/api -f
kubectl -n kp exec -it deploy/api -- sh
kubectl -n ingress-nginx get pods,svc
curl.exe -H "Host: kp.local" http://127.0.0.1:8088/api/health
helm -n kp status kp
```

Windows hosts (admin): `C:\Windows\System32\drivers\etc\hosts` → `127.0.0.1 kp.local`

## Docker Compose (local without K8s)

```bash
make demo          # api + frontend + data plane
make llm-ollama    # + ollama (profile llm) + ollama-pull.ps1
.\scripts\ollama-pull.ps1   # model with retries
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
