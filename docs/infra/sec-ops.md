# DevSecOps / K8s security lab

Короткий путь: **база → сканеры → аудит своего `kp`**.  
Цель — найти типовые мисконфиги и CVE на **этой** платформе и потренировать навыки аудита Kubernetes.

Стиль как [SRE.md](../SRE.md): готовые команды, минимум теории.

| Что это | Что не это |
|---------|------------|
| Авторизованный аудит **своего** локального кластера | Гайды по взлому чужих систем |
| Сканеры Trivy / Semgrep + `kubectl` checklist | Kali / Metasploit / Burp пошагово |
| Кластерная и supply-chain безопасность | App ACL / guardrails ([ADR-005](../adr/ADR-005-security.md)) |

Инфра: [compose-dev.md](compose-dev.md) · [k8s-architecture.md](k8s-architecture.md) · Compose сканеров: [`infra/docker-compose.sec-ops.yml`](../../infra/docker-compose.sec-ops.yml).

**ОС:** ниже блоки **Windows (PowerShell)** и **macOS (zsh/bash)**. `make` работает на обеих, если установлен GNU Make.

---

## Правила

1. Сканируй только **свой** Docker Desktop / kind и namespace `kp`.
2. Не направляй Nmap/сканеры на чужие сети и чужие IP.
3. Findings ниже — учебные (desktop-chart), не prod-hardening checklist компании.

---

## База за выходные (чеклист)

### Kubernetes

| Тема | Достаточно знать |
|------|------------------|
| Сущности | Pod, Deployment, ServiceAccount, Secret, Service, Ingress, Namespace |
| RBAC | Role/ClusterRole + Binding; кто и что может через API |
| Сеть | NetworkPolicy есть / нет; flat network = любой pod → любой |
| Привилегии | `privileged`, `hostPath`, `docker.sock`, `hostNetwork` |
| Путь риска | `Pod → SA token → RBAC → Secrets / privileged → Node` |

Команды: `kubectl get`, `describe`, `auth can-i`.

### Shell (Bash / PowerShell)

| Навык | Windows | macOS |
|-------|---------|-------|
| Поиск в YAML | `Select-String` | `grep -E` |
| Сканеры | `docker compose run --rm` | то же |
| Отчёты | `tmp\sec-ops\` | `tmp/sec-ops/` |

### Python

Хватит читать JSON и печатать CRITICAL/HIGH. Пример: [`scripts/sec-parse-trivy.py`](../../scripts/sec-parse-trivy.py).

### Инструменты «на потом»

| Инструмент | Когда понадобится |
|------------|-------------------|
| Nmap | Разведка сетевых портов (не в этом lab) |
| Burp | Ручной аудит HTTP API / UI |
| Semgrep / Trivy | Уже в lab ниже |

---

## Предусловия

Нужны: Docker Desktop (или kind), `kubectl`, `helm`, `docker`. Образы `kp-api:dev` / `kp-frontend:dev` собираются в `k8s-up`.

**Windows**

```powershell
make demo
# или: .\scripts\hybrid-up.ps1
# или только кластер: .\scripts\k8s-up.ps1
kubectl -n kp get pods
```

**macOS**

```bash
make demo
# или: bash scripts/hybrid-up.sh
# или только кластер: bash scripts/k8s-up.sh
kubectl -n kp get pods
```

---

## Быстрый старт (один проход)

Скрипты: [`sec-scan.ps1`](../../scripts/sec-scan.ps1) (Windows) · [`sec-scan.sh`](../../scripts/sec-scan.sh) (macOS).

| Шаг | Результат |
|-----|-----------|
| kubectl checklist | `tmp/sec-ops/kubectl-audit.txt` |
| Trivy images | `tmp/sec-ops/trivy-*.json` (+ parse) |
| Semgrep `backend/` | `tmp/sec-ops/semgrep.json` |

**Windows**

```powershell
make sec-scan
# или: .\scripts\sec-scan.ps1
```

**macOS**

```bash
make sec-scan
# или: bash scripts/sec-scan.sh
```

Отчёты в `tmp/sec-ops/` (в git не коммитятся).

### Вручную (одинаково, кроме переноса строк)

**Windows**

```powershell
docker compose -f infra/docker-compose.sec-ops.yml run --rm trivy image --severity HIGH,CRITICAL kp-api:dev
docker compose -f infra/docker-compose.sec-ops.yml run --rm semgrep semgrep --config=auto /src/backend
```

**macOS**

```bash
docker compose -f infra/docker-compose.sec-ops.yml run --rm trivy image --severity HIGH,CRITICAL kp-api:dev
docker compose -f infra/docker-compose.sec-ops.yml run --rm semgrep semgrep --config=auto /src/backend
```

---

## Лаборатория на `kp` (4 шага)

### 1. Разведка namespace

**Windows**

```powershell
kubectl -n kp get deploy,svc,ingress,sa,secret,networkpolicy
kubectl -n kp get pods -o wide
kubectl get clusterrolebinding -o wide | Select-String "kp|cluster-admin"
```

**macOS**

```bash
kubectl -n kp get deploy,svc,ingress,sa,secret,networkpolicy
kubectl -n kp get pods -o wide
kubectl get clusterrolebinding -o wide | grep -E "kp|cluster-admin"
```

Запиши: сколько Deployments, есть ли Ingress, есть ли NetworkPolicy, какие Secrets.

### 2. Мисконфиги (privileged / host / RBAC)

**Windows**

```powershell
kubectl -n kp get pods -o yaml | Select-String -Pattern "privileged:|hostNetwork:|hostPath:|docker.sock"

kubectl auth can-i --list --as=system:serviceaccount:kp:default -n kp
kubectl auth can-i get secrets --as=system:serviceaccount:kp:default -n kp
kubectl auth can-i create pods --as=system:serviceaccount:kp:default -n kp

kubectl -n kp get pods -o jsonpath="{range .items[*]}{.metadata.name}{'\t'}{.spec.serviceAccountName}{'\n'}{end}"
```

**macOS**

```bash
kubectl -n kp get pods -o yaml | grep -E 'privileged:|hostNetwork:|hostPath:|docker.sock'

kubectl auth can-i --list --as=system:serviceaccount:kp:default -n kp
kubectl auth can-i get secrets --as=system:serviceaccount:kp:default -n kp
kubectl auth can-i create pods --as=system:serviceaccount:kp:default -n kp

kubectl -n kp get pods -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.spec.serviceAccountName}{"\n"}{end}'
```

### 3. Trivy — образы и манифесты

Команды compose одинаковы на обеих ОС.

```bash
# CVE в образах
docker compose -f infra/docker-compose.sec-ops.yml run --rm trivy image -f json -o /out/trivy-api.json kp-api:dev
docker compose -f infra/docker-compose.sec-ops.yml run --rm trivy image -f json -o /out/trivy-frontend.json kp-frontend:dev

# Мисконфиги в Helm chart
docker compose -f infra/docker-compose.sec-ops.yml run --rm trivy config /src/infra/helm/knowledge-platform

# Краткая сводка CRITICAL/HIGH
python scripts/sec-parse-trivy.py tmp/sec-ops/trivy-api.json   # Windows / macOS (или python3)
```

### 4. Semgrep — код backend

**Windows**

```powershell
docker compose -f infra/docker-compose.sec-ops.yml run --rm semgrep `
  semgrep --config=auto --json -o /out/semgrep.json /src/backend
```

**macOS**

```bash
docker compose -f infra/docker-compose.sec-ops.yml run --rm semgrep \
  semgrep --config=auto --json -o /out/semgrep.json /src/backend
```

Опционально: `/src/frontend` тем же сервисом.

---

## Что ожидать на этом chart (учебные findings)

| Наблюдение | Почему так в MVP | Направление fix |
|------------|------------------|-----------------|
| Нет `NetworkPolicy` | Desktop-демо, flat network | default-deny + allowlist |
| Пароли/DSN в env values | Простой Helm для ноутбука | Secret / External Secrets / Vault |
| Слабый / нет `securityContext` | Не PSS Restricted | `runAsNonRoot`, drop caps, readOnlyRootFilesystem |
| Ingress наружу (`kp.local`) | Нужен UI для демо | Auth на edge, не светить NodePort без нужды |
| Default SA у подов | Chart без отдельных SA | отдельный SA + минимальный Role |

App-level ACL (роли guest/manager) — это [ADR-005](../adr/ADR-005-security.md), не замена кластерному аудиту.

---

## Мини-отчёт (шаблон)

Для каждого finding:

```text
Finding:   <что нашли>
Evidence:  <команда / файл / строка>
Impact:    <что может атакующий>
Fix:       <как закрыть (building)>
Severity:  Critical | High | Medium | Low
```

Пример:

```text
Finding:   В namespace kp нет NetworkPolicy
Evidence:  kubectl -n kp get networkpolicy → No resources found
Impact:    Любой pod в кластере может ходить к postgres/neo4j/redis по ClusterIP
Fix:       NetworkPolicy default-deny + allow api→postgres, api→neo4j, …
Severity:  High
```

На техсобесе удобная рамка: **misconfig → impact → fix**, без живого эксплойта.

---

## Zero-overlap: где что живёт

| Слой | Где |
|------|-----|
| Platform (api, stores, …) | Kubernetes `kp` |
| Ollama + Prometheus/Grafana/Jaeger | Compose `docker-compose.yml` |
| Trivy + Semgrep (ephemeral) | Compose `docker-compose.sec-ops.yml` |

Сканеры **не** дублируют postgres/api и не держат долгоживущие контейнеры — только `compose run --rm`.

### Trivy: ERROR `[rego] … specify_ami_owners / requestedamis`

Это **не** finding по вашему chart. Старый Trivy качает свежий policy-bundle с AWS-проверками, которые он не понимает; check пропускается, скан Helm идёт дальше (`Detected config files`). В lab стоит образ `aquasec/trivy:0.61.1+`. Если логи всё ещё шумят — просто игнорируйте AWS `[rego]` строки.
