# SRE / ops runbook (curl, kubectl, Helm, Compose)

Operations cheat sheet for the **RetailPartnerX Knowledge Platform** (Docker Desktop + Helm).  
Detailed setup (Win + Mac): [SETUP.md](SETUP.md). Infrastructure: [infra/](infra/). Audit: [infra/sec-ops.md](infra/sec-ops.md) (`make sec-scan`).

**OS:** **Windows** blocks (`curl.exe`, PowerShell `` ` ``) and **macOS** blocks (`curl`, bash `\`). Where the commands are identical, there is a single `bash` block.

## Context and URLs

| Mode | UI | API (health) |
|-------|-----|----------------|
| **Hybrid** (recommended) | http://kp.local:8088 | http://kp.local:8088/api/health |

Hosts → `127.0.0.1 kp.local`:

| OS | File |
|----|------|
| Windows | `C:\Windows\System32\drivers\etc\hosts` (admin) |
| macOS | `/etc/hosts` (`sudo`), see [SETUP.md](SETUP.md) |

Ingress listens on **:8088** (on Windows, `:80` is often taken by IIS).

---

## Ollama: where the model lives

| API location | Ollama location | Base URL for the API |
|---------|------------|------------------|
| K8s `deploy/api` (hybrid) | Compose | `http://host.docker.internal:11434/v1` |
| API on the host + Compose ollama | Compose | `http://localhost:11434/v1` |

The LLM page in the UI shows the same URL. It is **not** an address for the browser; it is where the **API** calls Ollama. For Docker Desktop K8s + Compose Ollama, `host.docker.internal` is the correct host; `localhost` in Apply breaks the probe (localhost inside the pod is not Ollama on the host).

`ollama pull` does **not** put the model into the pods; it goes into the Compose container. After changing env in Helm or using Apply in the UI, it is enough to **restart only `deploy/api`** (or run `helm upgrade`), not the whole namespace.

Start Ollama and download the model:

**Windows**

```powershell
make llm-ollama
curl.exe http://127.0.0.1:11434/v1/models
```

**macOS**

```bash
make llm-ollama
curl http://127.0.0.1:11434/v1/models
```

Connect the API in K8s to Compose Ollama (Helm overlay):

**Windows**

```powershell
cd yuit-docs-ai-architect-platform
helm upgrade kp app/infra/helm/knowledge-platform -n kp `
  -f app/infra/helm/knowledge-platform/values-desktop.yaml `
  -f app/infra/helm/knowledge-platform/values-desktop-compose-ollama.yaml `
  --wait --timeout 5m
kubectl -n kp rollout restart deploy/api
kubectl -n kp rollout status deploy/api --timeout=120s
```

**macOS**

```bash
cd yuit-docs-ai-architect-platform
helm upgrade kp app/infra/helm/knowledge-platform -n kp \
  -f app/infra/helm/knowledge-platform/values-desktop.yaml \
  -f app/infra/helm/knowledge-platform/values-desktop-compose-ollama.yaml \
  --wait --timeout 5m
kubectl -n kp rollout restart deploy/api
kubectl -n kp rollout status deploy/api --timeout=120s
```

Full hybrid (no Compose↔K8s duplicates):

| OS | Command |
|----|---------|
| Windows | `make demo` or `.\app\scripts\hybrid\hybrid-up.ps1` |
| macOS | `make demo` or `bash app/scripts/hybrid/hybrid-up.sh` |

In-cluster Ollama was removed from Helm; it runs only in Compose.

---

## curl: smoke tests and API

### Compose (direct API)

**Windows:** `curl.exe` · **macOS:** `curl` (the commands below are for macOS; on Windows, replace with `curl.exe`).

```bash
curl -s http://127.0.0.1:8080/health
curl -s http://127.0.0.1:8080/v1/llm/config
curl -s http://127.0.0.1:8080/v1/llm/health
curl -s http://127.0.0.1:8080/metrics
```

### K8s hybrid (NodePort metrics + ingress API)

**Windows**

```powershell
curl.exe -s http://127.0.0.1:30080/metrics | Select-String "kp_requests_total|rag_latency"
curl.exe -s -H "Host: kp.local" http://127.0.0.1:8088/api/health
curl.exe -s -H "Host: kp.local" http://127.0.0.1:8088/api/v1/llm/config
curl.exe -s -H "Host: kp.local" http://127.0.0.1:8088/api/v1/llm/health
```

**macOS**

```bash
curl -s http://127.0.0.1:30080/metrics | grep -E "kp_requests_total|rag_latency"
curl -s -H "Host: kp.local" http://127.0.0.1:8088/api/health
curl -s -H "Host: kp.local" http://127.0.0.1:8088/api/v1/llm/config
curl -s -H "Host: kp.local" http://127.0.0.1:8088/api/v1/llm/health
```

Prometheus targets: http://127.0.0.1:9090/targets (`kp-api-k8s` UP).  
Grafana: http://127.0.0.1:3000 → **Knowledge Platform / KP Overview** + Explore Tempo/Loki.  
Tempo: http://127.0.0.1:3200 → service `kp-api` after chat (UI through Grafana Explore).  
Loki: http://127.0.0.1:3100 → JSON logs API (Alloy).  
Diagram: [ADR-006](../architecture/adr/ADR-006-observability.md).

Expected in `/health`: `llm_provider`, `llm_reachable`, `store_backend`.

### Ollama (Compose)

```bash
curl -s http://127.0.0.1:11434/v1/models
curl -s http://127.0.0.1:11434/api/tags
```

### Runtime LLM config (Apply without the UI)

Roles: `Authorization: Bearer manager` or `Bearer compliance`.

**Windows (Compose)**

```powershell
curl.exe -s -X PUT http://127.0.0.1:8080/v1/llm/config `
  -H "Authorization: Bearer manager" `
  -H "Content-Type: application/json" `
  -d "{\"provider\":\"OLLAMA\",\"base_url\":\"http://host.docker.internal:11434/v1\",\"model\":\"qwen2.5:0.5b\"}"
```

**macOS (Compose)**

```bash
curl -s -X PUT http://127.0.0.1:8080/v1/llm/config \
  -H "Authorization: Bearer manager" \
  -H "Content-Type: application/json" \
  -d '{"provider":"OLLAMA","base_url":"http://host.docker.internal:11434/v1","model":"qwen2.5:0.5b"}'
```

**Windows (K8s ingress)**

```powershell
curl.exe -s -X PUT http://127.0.0.1:8088/api/v1/llm/config `
  -H "Host: kp.local" `
  -H "Authorization: Bearer manager" `
  -H "Content-Type: application/json" `
  -d "{\"provider\":\"OLLAMA\",\"base_url\":\"http://host.docker.internal:11434/v1\",\"model\":\"qwen2.5:0.5b\"}"
```

**macOS (K8s ingress)**

```bash
curl -s -X PUT http://127.0.0.1:8088/api/v1/llm/config \
  -H "Host: kp.local" \
  -H "Authorization: Bearer manager" \
  -H "Content-Type: application/json" \
  -d '{"provider":"OLLAMA","base_url":"http://host.docker.internal:11434/v1","model":"qwen2.5:0.5b"}'
```

> Apply at runtime does not change the pod's env; after `helm upgrade` with new `LLM_*` values, restarting `deploy/api` picks them up.

### Observability (Compose) + MinIO (K8s)

**Windows**

```powershell
make obs
curl.exe -s -o NUL -w "%{http_code}" http://127.0.0.1:9090/-/healthy
curl.exe -s -o NUL -w "%{http_code}" http://127.0.0.1:3000/api/health
curl.exe -s -o NUL -w "%{http_code}" http://127.0.0.1:3200/ready
curl.exe -s -o NUL -w "%{http_code}" http://127.0.0.1:3100/ready

kubectl -n kp port-forward svc/minio 9000:9000 9001:9001
curl.exe -s -o NUL -w "%{http_code}" http://127.0.0.1:9000/minio/health/live
```

**macOS**

```bash
make obs
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:9090/-/healthy
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:3000/api/health
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:3200/ready
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:3100/ready

kubectl -n kp port-forward svc/minio 9000:9000 9001:9001
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:9000/minio/health/live
```

---

## kubectl

The same on Windows and macOS:

```bash
kubectl config use-context docker-desktop
kubectl get nodes

kubectl -n kp get pods
kubectl -n kp get pods -o wide
kubectl -n kp get pods -w
kubectl -n kp get all,ingress
kubectl -n ingress-nginx get pods,svc

kubectl -n kp describe pod <pod-name>
kubectl -n kp logs deploy/api -f
kubectl -n kp logs deploy/frontend --tail=50
kubectl -n kp logs deploy/neo4j --tail=100
kubectl -n kp logs deploy/minio --tail=50

kubectl -n kp exec -it deploy/api -- sh

kubectl -n kp rollout restart deploy/api
kubectl -n kp rollout status deploy/api --timeout=120s
kubectl -n kp rollout restart deploy/frontend

# port-forward (bypasses ingress)
kubectl -n kp port-forward svc/api 8080:8080
kubectl -n kp port-forward svc/frontend 5173:80
```

---

## Helm

**Windows**

```powershell
helm -n kp list
helm -n kp status kp
helm -n kp get values kp

helm upgrade --install kp app/infra/helm/knowledge-platform -n kp --create-namespace `
  -f app/infra/helm/knowledge-platform/values-desktop.yaml `
  --wait --timeout 5m

.\app\scripts\k8s\k8s-down.ps1
```

**macOS**

```bash
helm -n kp list
helm -n kp status kp
helm -n kp get values kp

helm upgrade --install kp app/infra/helm/knowledge-platform -n kp --create-namespace \
  -f app/infra/helm/knowledge-platform/values-desktop.yaml \
  --wait --timeout 5m

bash app/scripts/k8s/k8s-down.sh
```

---

## Docker Compose

```bash
make demo              # hybrid (Win→.ps1, Mac→.sh)
make side              # ollama + obs only
make down
make sec-scan          # DevSecOps lab → tmp/sec-ops/

docker compose -f app/infra/docker-compose.yml --profile obs --profile llm ps
docker compose -f app/infra/docker-compose.yml logs ollama --tail=50
```

Model pull: Windows `.\app\scripts\ollama\ollama-pull.ps1 -Model qwen2.5:0.5b` · macOS `bash app/scripts/ollama/ollama-pull.sh qwen2.5:0.5b`

---

## Browser vs curl (502 / proxy)

If **curl** to `127.0.0.1:8088` works but Chrome returns 502, check the system proxy (for example Hiddify). Add `kp.local` and `127.0.0.1` to the bypass list / ProxyOverride.

---

## Quick checklist after LLM changes

1. `curl` Ollama `:11434/v1/models` → 200, model is listed  
2. `helm upgrade` with `values-desktop-compose-ollama.yaml` **or** PUT `/v1/llm/config`  
3. `kubectl -n kp rollout restart deploy/api` (if the Helm env changed)  
4. `curl` `/api/health` → `llm_provider=OLLAMA`, `llm_reachable=true`  
5. UI Chat → answer whose `model_uri` is not `mock://`

## Why the chat may answer oddly

- **`qwen2.5:0.5b`** is a tiny laptop model with weak coherence and style. Demo quality is higher on MOCK or 1.5b+.
- GraphRAG answers **only from the seed KB** (`datasets/seed`). If a fact is not in the base, you get "insufficient context", not the model's general knowledge.
- MOCK embeddings used to return the top 5 even for a garbage query; a lexical overlap filter + score floor now handle this.
- Good demo questions: FreshFarm / oats / gluten / nuts / cottage cheese / milk / allergen policy / secret promo (by role).

## Chat answer quality (this is not training)

The model is **not trained further** on the KB. GraphRAG: retrieval → prompt → `qwen2.5:0.5b` (tiny, for a laptop).

| Symptom | Why |
|---------|--------|
| Nonsense or a pile of unrelated policies | MOCK embeddings used to always return the top 5, and 0.5b summarized the noise. A lexical filter + score floor now apply |
| No facts about a product | The product is not in `datasets/seed` |
| You want better style | Use a larger model (`1.5b`+) or MOCK for a deterministic demo |

Demo questions with seed data: FreshFarm / oats, cottage cheese / FarmSoft, gluten/nuts allergens, ACL promo 42%.
