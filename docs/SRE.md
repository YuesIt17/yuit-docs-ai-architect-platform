# SRE / ops runbook (curl, kubectl, Helm, Compose)

Шпаргалка для эксплуатации **RetailPartnerX Knowledge Platform** на Windows (Docker Desktop + Helm). Подробный setup: [SETUP.md](SETUP.md).

## Контекст и URL

| Режим | UI | API (health) |
|-------|-----|----------------|
| Compose | http://localhost:5173 | http://localhost:8080/health |
| K8s (ingress) | http://kp.local:8088 | http://kp.local:8088/api/health |

Hosts (admin): `C:\Windows\System32\drivers\etc\hosts` → `127.0.0.1 kp.local`

Ingress слушает **:8088** (на Windows `:80` часто занят IIS).

---

## Ollama: где живёт модель

| Где API | Где Ollama | Base URL для API |
|---------|------------|------------------|
| Compose (`api` service) | Compose `ollama` | `http://ollama:11434/v1` |
| Compose API на хосте | Compose на хосте | `http://localhost:11434/v1` |
| K8s `deploy/api` | Compose на хосте | `http://host.docker.internal:11434/v1` |

В UI на странице LLM отображается тот же URL — это **не** адрес для браузера, а то, куда **API** стучится в Ollama. Для Docker Desktop K8s + Compose-Ollama `host.docker.internal` — правильный хост; `localhost` в Apply сломает probe (localhost внутри пода ≠ Ollama на хосте).

Модель **не** попадает в поды при `ollama pull` — в контейнере Compose. После смены env в Helm или Apply в UI достаточно **перезапустить только `deploy/api`** (или `helm upgrade`), не весь namespace.

Поднять Ollama и скачать модель:

```powershell
make llm-ollama
curl.exe http://127.0.0.1:11434/v1/models
```

Подключить API в K8s к Compose-Ollama (Helm overlay):

```powershell
cd yuit-docs-ai-architect-platform
helm upgrade kp infra/helm/knowledge-platform -n kp `
  -f infra/helm/knowledge-platform/values-desktop.yaml `
  -f infra/helm/knowledge-platform/values-desktop-compose-ollama.yaml `
  --wait --timeout 5m
kubectl -n kp rollout restart deploy/api
kubectl -n kp rollout status deploy/api --timeout=120s
```

Или при полном подъёме: `$env:KP_LLM='compose-ollama'; .\scripts\k8s-up.ps1`

In-cluster Ollama (тяжело для ноутбука): `$env:KP_LLM='ollama'; .\scripts\k8s-up.ps1`

---

## curl — smoke и API

### Compose (прямой API)

```powershell
curl.exe -s http://127.0.0.1:8080/health
curl.exe -s http://127.0.0.1:8080/v1/llm/config
curl.exe -s http://127.0.0.1:8080/v1/llm/health
curl.exe -s http://127.0.0.1:8080/metrics
```

### K8s через ingress (нужен Host, если нет записи в hosts)

```powershell
$H = @{ Host = "kp.local" }
curl.exe -s -H "Host: kp.local" http://127.0.0.1:8088/api/health
curl.exe -s -H "Host: kp.local" http://127.0.0.1:8088/api/v1/llm/config
curl.exe -s -H "Host: kp.local" http://127.0.0.1:8088/api/v1/llm/health
```

Ожидание в `/health`: `llm_provider`, `llm_reachable`, `store_backend`.

### Ollama (Compose)

```powershell
curl.exe -s http://127.0.0.1:11434/v1/models
curl.exe -s http://127.0.0.1:11434/api/tags
```

### Runtime LLM config (Apply без UI)

Роли: `Authorization: Bearer manager` или `Bearer compliance`.

Compose:

```powershell
curl.exe -s -X PUT http://127.0.0.1:8080/v1/llm/config `
  -H "Authorization: Bearer manager" `
  -H "Content-Type: application/json" `
  -d "{\"provider\":\"OLLAMA\",\"base_url\":\"http://host.docker.internal:11434/v1\",\"model\":\"qwen2.5:0.5b\"}"
```

K8s (через ingress):

```powershell
curl.exe -s -X PUT http://127.0.0.1:8088/api/v1/llm/config `
  -H "Host: kp.local" `
  -H "Authorization: Bearer manager" `
  -H "Content-Type: application/json" `
  -d "{\"provider\":\"OLLAMA\",\"base_url\":\"http://host.docker.internal:11434/v1\",\"model\":\"qwen2.5:0.5b\"}"
```

> Apply в рантайме не меняет env пода — после `helm upgrade` с новым `LLM_*` перезапуск `deploy/api` подхватит values.

### MinIO / observability (Compose)

```powershell
curl.exe -s -o NUL -w "%{http_code}" http://127.0.0.1:9000/minio/health/live
curl.exe -s -o NUL -w "%{http_code}" http://127.0.0.1:9090/-/healthy
curl.exe -s -o NUL -w "%{http_code}" http://127.0.0.1:3000/api/health
curl.exe -s -o NUL -w "%{http_code}" http://127.0.0.1:16686
```

---

## kubectl

```powershell
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

# port-forward (обход ingress)
kubectl -n kp port-forward svc/api 8080:8080
kubectl -n kp port-forward svc/frontend 5173:80
```

Legacy kind: `.\scripts\k8s-expose.ps1` → http://kp.local:8088

---

## Helm

```powershell
helm -n kp list
helm -n kp status kp
helm -n kp get values kp

helm upgrade --install kp infra/helm/knowledge-platform -n kp --create-namespace `
  -f infra/helm/knowledge-platform/values-desktop.yaml `
  --wait --timeout 5m

.\scripts\k8s-down.ps1
```

---

## Docker Compose

```powershell
make demo
make llm-ollama
make obs
make down

docker compose -f infra/docker-compose.yml --profile demo ps
docker compose -f infra/docker-compose.yml logs api -f
docker compose -f infra/docker-compose.yml logs ollama --tail=50

.\scripts\ollama-pull.ps1 -Model qwen2.5:0.5b
```

---

## Браузер vs curl (502 / proxy)

Если **curl** к `127.0.0.1:8088` OK, а Chrome — 502, проверьте системный прокси (например Hiddify). Добавьте `kp.local` и `127.0.0.1` в bypass / ProxyOverride.

---

## Быстрый чеклист после изменений LLM

1. `curl` Ollama `:11434/v1/models` → 200, модель в списке  
2. `helm upgrade` с `values-desktop-compose-ollama.yaml` **или** PUT `/v1/llm/config`  
3. `kubectl -n kp rollout restart deploy/api` (если меняли Helm env)  
4. `curl` `/api/health` → `llm_provider=OLLAMA`, `llm_reachable=true`  
5. UI Chat → ответ с `model_uri` не `mock://`
