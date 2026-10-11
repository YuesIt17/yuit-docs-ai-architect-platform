# SRE / ops runbook (curl, kubectl, Helm, Compose)

Шпаргалка для эксплуатации **RetailPartnerX Knowledge Platform** (Docker Desktop + Helm).  
Подробный setup (Win + Mac): [SETUP.md](SETUP.md). Инфра: [infra/](infra/). Аудит: [infra/sec-ops.md](infra/sec-ops.md) (`make sec-scan`).

**ОС:** блоки **Windows** (`curl.exe`, PowerShell `` ` ``) и **macOS** (`curl`, bash `\`). Где команды одинаковы — один блок `bash`.

## Контекст и URL

| Режим | UI | API (health) |
|-------|-----|----------------|
| **Hybrid** (рекомендуется) | http://kp.local:8088 | http://kp.local:8088/api/health |
| Standalone Compose | http://localhost:5173 | http://localhost:8080/health |

Hosts → `127.0.0.1 kp.local`:

| ОС | Файл |
|----|------|
| Windows | `C:\Windows\System32\drivers\etc\hosts` (admin) |
| macOS | `/etc/hosts` (`sudo`), см. [SETUP.md](SETUP.md) |

Ingress слушает **:8088** (на Windows `:80` часто занят IIS).

---

## Ollama: где живёт модель

| Где API | Где Ollama | Base URL для API |
|---------|------------|------------------|
| K8s `deploy/api` (hybrid) | Compose | `http://host.docker.internal:11434/v1` |
| API на хосте + Compose ollama | Compose | `http://localhost:11434/v1` |

В UI на странице LLM отображается тот же URL — это **не** адрес для браузера, а то, куда **API** стучится в Ollama. Для Docker Desktop K8s + Compose-Ollama `host.docker.internal` — правильный хост; `localhost` в Apply сломает probe (localhost внутри пода ≠ Ollama на хосте).

Модель **не** попадает в поды при `ollama pull` — в контейнере Compose. После смены env в Helm или Apply в UI достаточно **перезапустить только `deploy/api`** (или `helm upgrade`), не весь namespace.

Поднять Ollama и скачать модель:

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

Подключить API в K8s к Compose-Ollama (Helm overlay):

**Windows**

```powershell
cd yuit-docs-ai-architect-platform
helm upgrade kp infra/helm/knowledge-platform -n kp `
  -f infra/helm/knowledge-platform/values-desktop.yaml `
  -f infra/helm/knowledge-platform/values-desktop-compose-ollama.yaml `
  --wait --timeout 5m
kubectl -n kp rollout restart deploy/api
kubectl -n kp rollout status deploy/api --timeout=120s
```

**macOS**

```bash
cd yuit-docs-ai-architect-platform
helm upgrade kp infra/helm/knowledge-platform -n kp \
  -f infra/helm/knowledge-platform/values-desktop.yaml \
  -f infra/helm/knowledge-platform/values-desktop-compose-ollama.yaml \
  --wait --timeout 5m
kubectl -n kp rollout restart deploy/api
kubectl -n kp rollout status deploy/api --timeout=120s
```

Полный hybrid (без дублей Compose↔K8s):

| ОС | Команда |
|----|---------|
| Windows | `make demo` или `.\scripts\hybrid-up.ps1` |
| macOS | `make demo` или `bash scripts/hybrid-up.sh` |

In-cluster Ollama убран из Helm — только Compose.

---

## curl — smoke и API

### Compose (прямой API)

**Windows:** `curl.exe` · **macOS:** `curl` (ниже — macOS; на Windows замените на `curl.exe`).

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
Grafana: http://127.0.0.1:3000 → **Knowledge Platform / KP Overview**.  
Jaeger: http://127.0.0.1:16686 → service `kp-api` после chat.

Ожидание в `/health`: `llm_provider`, `llm_reachable`, `store_backend`.

### Ollama (Compose)

```bash
curl -s http://127.0.0.1:11434/v1/models
curl -s http://127.0.0.1:11434/api/tags
```

### Runtime LLM config (Apply без UI)

Роли: `Authorization: Bearer manager` или `Bearer compliance`.

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

> Apply в рантайме не меняет env пода — после `helm upgrade` с новым `LLM_*` перезапуск `deploy/api` подхватит values.

### Observability (Compose) + MinIO (K8s)

**Windows**

```powershell
make obs
curl.exe -s -o NUL -w "%{http_code}" http://127.0.0.1:9090/-/healthy
curl.exe -s -o NUL -w "%{http_code}" http://127.0.0.1:3000/api/health
curl.exe -s -o NUL -w "%{http_code}" http://127.0.0.1:16686

kubectl -n kp port-forward svc/minio 9000:9000 9001:9001
curl.exe -s -o NUL -w "%{http_code}" http://127.0.0.1:9000/minio/health/live
```

**macOS**

```bash
make obs
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:9090/-/healthy
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:3000/api/health
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:16686

kubectl -n kp port-forward svc/minio 9000:9000 9001:9001
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:9000/minio/health/live
```

---

## kubectl

Одинаково на Windows и macOS:

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

# port-forward (обход ingress)
kubectl -n kp port-forward svc/api 8080:8080
kubectl -n kp port-forward svc/frontend 5173:80
```

Legacy kind: Windows `.\scripts\k8s-expose.ps1` · macOS `bash scripts/k8s-expose.sh` → http://kp.local:8088

---

## Helm

**Windows**

```powershell
helm -n kp list
helm -n kp status kp
helm -n kp get values kp

helm upgrade --install kp infra/helm/knowledge-platform -n kp --create-namespace `
  -f infra/helm/knowledge-platform/values-desktop.yaml `
  --wait --timeout 5m

.\scripts\k8s-down.ps1
```

**macOS**

```bash
helm -n kp list
helm -n kp status kp
helm -n kp get values kp

helm upgrade --install kp infra/helm/knowledge-platform -n kp --create-namespace \
  -f infra/helm/knowledge-platform/values-desktop.yaml \
  --wait --timeout 5m

bash scripts/k8s-down.sh
```

---

## Docker Compose

```bash
make demo              # hybrid (Win→.ps1, Mac→.sh)
make side              # ollama + obs only
make demo-standalone   # full stack WITHOUT k8s — mutually exclusive
make down
make sec-scan          # DevSecOps lab → tmp/sec-ops/

docker compose -f infra/docker-compose.yml --profile obs --profile llm ps
docker compose -f infra/docker-compose.yml logs ollama --tail=50
```

Pull модели: Windows `.\scripts\ollama-pull.ps1 -Model qwen2.5:0.5b` · macOS `bash scripts/ollama-pull.sh qwen2.5:0.5b`

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

## Почему чат «отвечает странно»

- **`qwen2.5:0.5b`** — крошечная модель для ноутбука; связность/стиль слабые. Качество демо выше на MOCK или 1.5b+.
- GraphRAG отвечает **только из seed KB** (`datasets/seed`). Нет факта в базе → «недостаточно контекста», а не общие знания модели.
- Раньше MOCK-embeddings всегда отдавали top‑5 даже по мусорному запросу; теперь фильтр по lexical overlap + score floor.
- Хорошие демо-вопросы: FreshFarm / oats / gluten / nuts / творог / молоко / allergen policy / secret promo (по роли).

## Качество ответов чата (не «обучение»)

Модель **не дообучается** на KB. GraphRAG: retrieval → промпт → `qwen2.5:0.5b` (tiny, для ноутбука).

| Симптом | Почему |
|---------|--------|
| Бред / «Возможно, вы не знаете…» + куча чужих политик | Раньше MOCK-embeddings всегда отдавали top‑5; 0.5b «суммировал» шум. Сейчас lexical filter + score floor |
| Нет фактов про продукт | Продукта нет в `datasets/seed` |
| Хочется нормальный стиль | Больше модель (`1.5b`+) или MOCK для детерминированного демо |

Демо-вопросы с seed: FreshFarm / овсянка, творог / FarmSoft, аллергены gluten/nuts, ACL promo 42%.
