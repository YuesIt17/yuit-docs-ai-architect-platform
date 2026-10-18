# DevSecOps / Security Engineer lab

Короткий путь: **база → сканеры → аудит своего `kp` → отчёт (breaking) → fix (building)**.  
Цель — потренировать обязанности Security Engineer на **этой** платформе: внутренний контур, Web/API, K8s, оркестрация сканеров, Vulnerability Management и handoff в SOC — без атак на чужие системы.

Стиль как [SRE.md](../SRE.md): готовые команды, минимум теории.

| Что это | Что не это |
|---------|------------|
| Авторизованный аудит **своего** локального кластера / `kp.local` | Гайды по взлому чужих систем |
| Сканеры + `kubectl` + шаблоны отчётов / IoC | Пошаговый Metasploit / готовые exploit PoC |
| Breaking **и** building (misconfig → impact → Helm/fix) | Только «нашли CVE и ушли» |
| Кластерная и supply-chain безопасность | App ACL / guardrails ([ADR-005](../adr/ADR-005-security.md)) |

Инфра: [compose-dev.md](compose-dev.md) · [k8s-architecture.md](k8s-architecture.md) · Compose сканеров: [`infra/docker-compose.sec-ops.yml`](../../infra/docker-compose.sec-ops.yml).

**ОС:** блоки **Windows (PowerShell)** и **macOS (zsh/bash)**. `make` работает на обеих, если установлен GNU Make.

---

## Карта обязанностей → этот lab

| Обязанность / навык (JD) | В этом lab | Вне lab (работа / отдельный стенд) |
|--------------------------|------------|-------------------------------------|
| Авто + ручной пентест (внутренний контур, Web, API, сегменты) | Nmap, ZAP, Nuclei, Semgrep, kubectl; ручной обход UI/API | Burp Suite, Nessus, полный red-team scope |
| Аудит облака (OpenStack) и контейнеров (K8s) | K8s: RBAC, NetPol, PSS, Trivy, kube-bench, Checkov | OpenStack — чеклист ниже (без стенда в репо) |
| PoC / демонстрация риска бизнесу | Report: evidence → impact → fix (бизнес-язык) | Live exploit PoC — **не** в этом репо |
| Red team exercises (critical assets) | Рамка сценария на активах `kp` | Kali/Parrot + Metasploit на authorized engagement |
| Оркестрация сканеров (Python/Bash) + разбор JSON | `make sec-scan`, `sec-parse-*.py` | Burp Enterprise / Nessus API на работе |
| Hardening K8s (RBAC, NetPol, PSS / Gatekeeper, admission) | Checklist + building-fixes; Checkov/Trivy config | OPA Gatekeeper / Kyverno в shared/prod cluster |
| Vulnerability Management как сервис | Жизненный цикл на `tmp/sec-ops/` | Jira/ServiceNow + SLA компании |
| Handoff SOC / Blue Team (IoC) | Шаблон IoC ниже | Реальный SIEM / ticketing |
| Kali / Parrot, Burp, Metasploit, Nmap | Nmap (+ ZAP) в compose; остальное — внешний toolchain | Установка Kali/Burp/msf на host |
| Python / Bash автоматизация | Скрипты `scripts/sec/sec-scan.*`, parse helpers | Расширение оркестрации под corp scanners |
| Архитектура K8s (etcd, apiserver, CNI) | База ниже + аудит namespace | Deep dive control-plane на bare-metal/cloud |
| Breaking ↔ building | Таблица findings + направление Helm fix | PR с заказчиком платформы |
| Клиентоориентированность | Шаблон отчёта для внутренних заказчиков | Стейкхолдер-митинги |
| Самостоятельность + эскалация | Средние findings сами; критерии эскалации Senior/Lead | — |

---

## Правила и scope

1. Сканируй только **свой** Docker Desktop / kind и namespace `kp`.
2. Nmap / ZAP / Nuclei — только `127.0.0.1`, `kp.local`, `host.docker.internal` (из контейнера). Не направляй сканеры на чужие сети и чужие IP.
3. Findings ниже — учебные (desktop-chart), не prod-hardening checklist компании.
4. Finding без **building**-рекомендации считается незакрытым шагом lab.
5. В репозитории **нет** готовых exploit PoC и Metasploit-модулей: риск показываем отчётом и фиксом.

Из контейнеров Compose цель для Ingress — **`http://host.docker.internal:8088`** (на host в браузере — `http://kp.local:8088`).

---

## Глоссарий (термины lab)

| Термин | Что это | Зачем Security Engineer |
|--------|---------|-------------------------|
| **DevSecOps** | Безопасность встроенная в разработку и поставку (scan → fix → CI), не «отдел в конце» | Роль lab: ловить misconfig/CVE до prod |
| **внутренний контур** | Сеть/сервисы внутри компании или локального стенда, не публичный интернет | Типичный scope пентеста / аудита |
| **kp / `kp.local`** | Namespace и hostname нашей Knowledge Platform | Единственная учебная цель сканеров |
| **finding** | Конкретная находка (misconfig, CVE, открытый порт) с evidence | Единица отчёта и triage |
| **breaking / building** | Сломать/найти риск → предложить и сделать fix | Полный цикл Security Engineer, не только «нашли» |
| **misconfig** | Небезопасная настройка (нет NetPol, privileged, secrets в values) | Чаще реальный риск, чем «голый» CVE |
| **PoC** | Proof of Concept — демонстрация, что риск реален | Здесь: narrative + evidence в отчёте, не exploit в git |
| **RBAC** | Role-Based Access Control — кто что может через API | Аудит `can-i`, ClusterRoleBinding, SA |
| **SA** | ServiceAccount — идентичность Pod'а в API | Украденный token + широкие права = путь к Secrets |
| **NetPol** | NetworkPolicy — firewall pod↔pod | Без неё сеть плоская: любой pod → postgres |
| **PSS** | Pod Security Standards (Privileged / Baseline / Restricted) | Политика «какие Pod вообще можно создать» |
| **Admission** | Контроллеры, проверяющие объект **до** create/update | Gatekeeper / Kyverno / PSS — блок privileged, hostPath |
| **OPA Gatekeeper / Kyverno** | Policy engines в кластере (правила как код) | В lab не ставим; направление для prod |
| **CNI** | Container Network Interface — как Pod'ы получают IP и маршруты | База для сегментации; NetPol работает поверх CNI |
| **CIS** | Center for Internet Security — бенчмарки «как должно быть» | kube-bench проверяет CIS Kubernetes |
| **CVE** | Известная уязвимость в ПО (номер в базе) | Trivy находит CVE в образах; triage по severity + контексту |
| **IaC** | Infrastructure as Code (Helm, Terraform, манифесты) | Checkov / Trivy config — политики на YAML до деплоя |
| **supply-chain** | Цепочка сборки/образов/зависимостей | Скан image + pin digest + CI gate |
| **Vulnerability Management** | Процесс: найти → оценить → ticket → fix → verify | Сервис, а не разовый отчёт сканера |
| **triage** | Разбор: ложный позитив? severity? приоритет fix? | Без triage сканер = шум |
| **SOC / Blue Team** | Центр мониторинга / защитники (детект, реагирование) | Им передаём IoC после теста |
| **IoC** | Indicator of Compromise — IP, hash, URL, SA для hunt/block | Шаблон handoff ниже |
| **SIEM** | Система сбора логов и алертов (работа) | Вне lab; здесь только формат IoC |
| **IMDS** | Instance Metadata Service в облаке (credentials с VM) | Аналог риска: SA token / cloud metadata из pod |
| **blast radius** | Насколько далеко «разлетится» компромисс | etcd / hostPath / docker.sock → почти весь кластер |
| **ephemeral** | Контейнер сканера живёт только на время `compose run` | Не держит БД/API; не пересекается с `kp` |
| **FOSS** | Free/Open Source Software | ZAP = бесплатный стенд вместо Burp в lab |
| **RCE** | Remote Code Execution — удалённое выполнение кода | Критичный класс; эскалация Senior/Lead |
| **JD** | Job Description — требования вакансии | Колонка «обязанность» в карте выше |

Сущности K8s (Pod, Deployment, Secret, Ingress…): [k8s-primer.md](k8s-primer.md).

---

## База компетенций

### Kubernetes (control plane и путь атаки)

| Компонент | Что это | Зачем Security Engineer |
|-----------|---------|-------------------------|
| **kube-apiserver** | API-шлюз кластера | Единая точка authn/authz; все `kubectl` и контроллеры ходят сюда |
| **etcd** | Ключ-значение хранилище состояния | Secrets и конфиг at rest; доступ к etcd ≈ полный компромисс |
| **kubelet** | Агент на каждой Node, запускает контейнеры | Слабый kubelet API / privileged pod → выход на host |
| **CNI** | Плагин сети Pod'ов | Без NetworkPolicy сеть плоская (любой pod → любой) |
| **RBAC** | Роли и привязки к пользователям/SA | Кто и что может через API |
| **Admission** | Хуки до create (PSS / Gatekeeper / Kyverno) | Блокируют небезопасные Pod до появления в кластере |

Путь риска (запомнить): `Pod → SA token → RBAC → Secrets / privileged → Node`.

Сущности для аудита: Pod, Deployment, ServiceAccount, Secret, Service, Ingress, Namespace, NetworkPolicy.

Команды: `kubectl get`, `describe`, `auth can-i`.

### Shell (Bash / PowerShell) и Python

| Навык | Windows | macOS |
|-------|---------|-------|
| Поиск в YAML | `Select-String` | `grep -E` |
| Сканеры | `docker compose run --rm` | то же |
| Отчёты | `tmp\sec-ops\` | `tmp/sec-ops/` |
| Парсинг JSON | `python scripts/sec/sec-parse-trivy.py` · `sec-parse-summary.py` | то же |

### Toolchain matrix (что делает каждый инструмент)

Слои: **образ** → **код** → **IaC/Helm** → **кластер (CIS/RBAC)** → **сеть/порты** → **Web/API**. Один сканер не закрывает всё.

| Инструмент | Что делает | Зачем в lab / на работе | В lab |
|------------|------------|-------------------------|-------|
| **Trivy** | CVE в Docker-образах + базовые misconfig в YAML/Helm | «Что опасного в `kp-api:dev` и chart?» | compose |
| **Semgrep** | Статический анализ кода (правила SAST) | Найти типичные баги безопасности в `backend/` без запуска | compose |
| **Checkov** | Policy-as-code по IaC (Helm/K8s) | «Chart нарушает best practices?» (дополняет Trivy config) | compose |
| **Nmap** | Скан портов и версий сервисов | Что слушает host: Ingress 8088 и лишнее снаружи | compose → `host.docker.internal` |
| **Nuclei** | Шаблоны известных web/API уязвимостей | Быстрый авточек HTTP `kp.local` на известные паттерны | compose |
| **OWASP ZAP** | Авто/пассивный web-сканер (прокси) | FOSS-стенд Burp: baseline по UI/API | compose; `SEC_SCAN_DEEP=1` |
| **kube-bench** | Проверки CIS Kubernetes | Hardening control-plane/node/policies | compose; на Desktop часто skip |
| **Burp Suite** | Ручной proxy для Web/API (Repeater, Intruder…) | Глубокий ручной аудит на работе | внешний → `http://kp.local:8088` |
| **Nessus** | Корпоративный vuln-сканер инфраструктуры | Широкий infra-scan; в lab заменяем Trivy+Nmap+Checkov | внешний |
| **Kali / Parrot** | Дистрибутивы с пентест-тулчейном | Готовое окружение (Nmap, Burp, msf…) | внешний host |
| **Metasploit** | Фреймворк эксплуатации | Только authorized red team; **шагов exploit в этом doc нет** | внешний |

---

## OpenStack (концепт, без стенда в репо)

**Зачем блок:** в JD часто «аудит OpenStack»; стенда в репо нет — ниже маппинг «облако → тот же навык на `kp`».

| Область | Что это / смотреть | Аналог в `kp` / K8s |
|---------|--------------------|---------------------|
| Identity / RBAC | кто админ облака, лишние роли | K8s RBAC, SA bindings |
| Security groups | firewall VM: открытые `0.0.0.0/0`, лишние порты | NetworkPolicy, Ingress |
| Metadata / IMDS | HTTP-сервис на VM отдаёт cloud credentials | SA tokens в pod, cloud metadata |
| Images / volumes | устаревшие образы VM, публичные диски | Trivy image, registry policy |
| Tenant vs provider net | изоляция сетей арендаторов | CNI + NetPol |
| Logging / audit | кто менял SG / роли | Kubernetes audit logs, SIEM |

Этот репозиторий **не** поднимает OpenStack — только чеклист для собеса и переноса навыков.

---

## Предусловия

Нужны: Docker Desktop (или kind), `kubectl`, `helm`, `docker`. Образы `kp-api:dev` / `kp-frontend:dev` собираются в `k8s-up`.

**Windows**

```powershell
make demo
# или: .\scripts\hybrid\hybrid-up.ps1
# или только кластер: .\scripts\k8s\k8s-up.ps1
kubectl -n kp get pods
```

**macOS**

```bash
make demo
# или: bash scripts/hybrid/hybrid-up.sh
# или только кластер: bash scripts/k8s/k8s-up.sh
kubectl -n kp get pods
```

---

## Быстрый старт (один проход)

Скрипты: [`sec-scan.ps1`](../../scripts/sec/sec-scan.ps1) (Windows) · [`sec-scan.sh`](../../scripts/sec/sec-scan.sh) (macOS).

| Шаг | Результат |
|-----|-----------|
| kubectl checklist | `tmp/sec-ops/kubectl-audit.txt` |
| Trivy images + Helm config | `tmp/sec-ops/trivy-*.json` (+ parse) |
| Semgrep `backend/` | `tmp/sec-ops/semgrep.json` |
| Checkov (Helm) | `tmp/sec-ops/checkov.json` |
| Nmap (localhost Ingress) | `tmp/sec-ops/nmap.txt` |
| Nuclei | `tmp/sec-ops/nuclei.txt` |
| kube-bench (best-effort) | `tmp/sec-ops/kube-bench.txt` или skip |
| ZAP baseline | только при `SEC_SCAN_DEEP=1` → `tmp/sec-ops/zap-baseline.*` |
| Сводка counts | stdout от `sec-parse-summary.py` |

**Windows**

```powershell
make sec-scan
# или: .\scripts\sec\sec-scan.ps1

# глубокий проход (+ ZAP; дольше):
$env:SEC_SCAN_DEEP = "1"; make sec-scan
```

**macOS**

```bash
make sec-scan
# или: bash scripts/sec/sec-scan.sh

# глубокий проход (+ ZAP; дольше):
SEC_SCAN_DEEP=1 make sec-scan
```

Отчёты в `tmp/sec-ops/` (в git не коммитятся).

### Вручную (базовые сканеры)

**Windows / macOS** (compose-строки одинаковы)

```bash
docker compose -f infra/docker-compose.sec-ops.yml run --rm trivy image --severity HIGH,CRITICAL kp-api:dev
docker compose -f infra/docker-compose.sec-ops.yml run --rm semgrep semgrep --config=auto /src/backend
docker compose -f infra/docker-compose.sec-ops.yml run --rm checkov -d /src/infra/helm/knowledge-platform --framework kubernetes helm --soft-fail -o json --output-file-path /out
docker compose -f infra/docker-compose.sec-ops.yml run --rm nmap -sV -p 8088,80,443 -oN /out/nmap.txt host.docker.internal
docker compose -f infra/docker-compose.sec-ops.yml run --rm nuclei -u http://host.docker.internal:8088 -silent -o /out/nuclei.txt
```

ZAP (deep):

```bash
docker compose -f infra/docker-compose.sec-ops.yml run --rm zap \
  zap-baseline.py -t http://host.docker.internal:8088 -J /out/zap-baseline.json -I
```

---

## Лаборатория на `kp`

Каждый шаг = один слой защиты. Цель — собрать findings с evidence, не «прогнать все флаги».

### 1. Разведка namespace + sanity control plane

**Зачем:** понять поверхность атаки — что крутится, есть ли NetPol/Ingress/Secrets, не раздаётся ли `cluster-admin`.

**Windows**

```powershell
kubectl -n kp get deploy,svc,ingress,sa,secret,networkpolicy
kubectl -n kp get pods -o wide
kubectl get clusterrolebinding -o wide | Select-String "kp|cluster-admin"
kubectl get --raw='/readyz?verbose'   # apiserver health (если доступно)
```

**macOS**

```bash
kubectl -n kp get deploy,svc,ingress,sa,secret,networkpolicy
kubectl -n kp get pods -o wide
kubectl get clusterrolebinding -o wide | grep -E "kp|cluster-admin"
kubectl get --raw='/readyz?verbose'   # apiserver health (если доступно)
```

Запиши: сколько Deployments, есть ли Ingress, есть ли NetworkPolicy, какие Secrets, какие SA.

Critical assets для red-team рамки: Ingress `kp.local`, `deploy/api`, postgres / neo4j / redis / qdrant / minio (Data plane).

### 2. Мисконфиги (privileged / host / RBAC)

**Зачем:** типичный путь компромисса в K8s — privileged/hostPath/docker.sock и слишком широкие права default SA.

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

**Зачем:** CVE в `kp-api` / `kp-frontend` и грубые ошибки в Helm YAML (supply-chain + config).

```bash
docker compose -f infra/docker-compose.sec-ops.yml run --rm trivy image -f json -o /out/trivy-api.json kp-api:dev
docker compose -f infra/docker-compose.sec-ops.yml run --rm trivy image -f json -o /out/trivy-frontend.json kp-frontend:dev
docker compose -f infra/docker-compose.sec-ops.yml run --rm trivy config /src/infra/helm/knowledge-platform
python scripts/sec/sec-parse-trivy.py tmp/sec-ops/trivy-api.json
```

### 4. Semgrep — код backend

**Зачем:** SAST — найти в коде паттерны вроде небезопасного SQL/десериализации/секретов до деплоя.

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

### 5. Checkov — IaC / Helm policy

**Зачем:** policy-as-code по chart: нет securityContext, лишние capabilities, публичные Service и т.п.

```bash
docker compose -f infra/docker-compose.sec-ops.yml run --rm checkov \
  -d /src/infra/helm/knowledge-platform \
  --framework kubernetes helm --soft-fail \
  -o json --output-file-path /out
# отчёт: tmp/sec-ops/results_json.json (переименовывается скриптом в checkov.json)
```

### 6. Nmap — сегмент / открытые порты (только localhost)

**Зачем:** снаружи видно только то, что слушает host; лишний открытый порт = лишняя поверхность.

```bash
docker compose -f infra/docker-compose.sec-ops.yml run --rm nmap \
  -sV -p 8088,80,443,11434 -oN /out/nmap.txt host.docker.internal
```

На host можно сверить: `http://kp.local:8088`. Не сканируй другие подсети.

### 7. Nuclei — web/API templates

**Зачем:** быстрый прогон известных HTTP/API проверок (headers, path disclosure, типовые misconfig) по Ingress.

```bash
docker compose -f infra/docker-compose.sec-ops.yml run --rm nuclei \
  -u http://host.docker.internal:8088 -silent -o /out/nuclei.txt
```

### 8. OWASP ZAP — baseline (FOSS-стенд Burp)

**Зачем:** пассивный/базовый web-аудит UI и API (как упрощённый Burp без ручного proxy).  
Долгий шаг; в `make sec-scan` только при `SEC_SCAN_DEEP=1`.

```bash
docker compose -f infra/docker-compose.sec-ops.yml run --rm zap \
  zap-baseline.py -t http://host.docker.internal:8088 -J /out/zap-baseline.json -I
```

Ручной аналог на работе: Burp Suite против того же URL — **Proxy** (перехват трафика), **Repeater** (повтор/правка запроса), **Intruder** (перебор параметров); только по политике engagement.

### 9. kube-bench — CIS (best-effort)

**Зачем:** сверить кластер с CIS Kubernetes (шифр etcd, anon-auth, файлы ноды…). На Desktop часто skip — нет FS ноды.  
На kind/VM с доступом к ноде:

```bash
docker compose -f infra/docker-compose.sec-ops.yml run --rm kube-bench \
  run --targets policies 2>&1 | tee tmp/sec-ops/kube-bench.txt
```

Альтернатива в кластере: Job из документации Aqua kube-bench (не входит в compose).

### 10. Hardening direction (building)

**Зачем:** закрыть breaking-находки конкретными контролями (NetPol, PSS, RBAC, admission, image gate).  
В desktop-lab Gatekeeper обычно **не** ставим (тяжело для ноутбука). Направление для prod / shared cluster:

| Контроль | Что сделать |
|----------|-------------|
| NetworkPolicy | default-deny Ingress/Egress + allowlist api→stores |
| Pod Security | `securityContext`: `runAsNonRoot`, drop `ALL`, `readOnlyRootFilesystem`; namespace PSS Restricted |
| RBAC | отдельный SA на workload, минимальный Role, не default SA |
| Admission | OPA Gatekeeper / Kyverno: запрет privileged, hostPath, `:latest` |
| Images | Trivy в CI; не деплоить CRITICAL без exception |

Пример идеи NetworkPolicy (не применяется автоматически — building-черновик):

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-ingress
  namespace: kp
spec:
  podSelector: {}
  policyTypes: ["Ingress"]
```

Дальше — отдельные allow-правила `api → postgres/neo4j/redis/...` и Ingress controller → frontend/api.

---

## Breaking ↔ Building (типовые findings на этом chart)

| Наблюдение | Почему так в MVP | Building fix |
|------------|------------------|--------------|
| Нет `NetworkPolicy` | Desktop-демо, flat CNI | default-deny + allowlist |
| Пароли/DSN в env values | Простой Helm для ноутбука | Secret / External Secrets / Vault |
| Слабый / нет `securityContext` | Не PSS Restricted | `runAsNonRoot`, drop caps, readOnlyRootFilesystem |
| Ingress наружу (`kp.local`) | Нужен UI для демо | Auth на edge; не светить лишние NodePort |
| Default SA у подов | Chart без отдельных SA | отдельный SA + минимальный Role |
| CVE CRITICAL/HIGH в образах | Базовый image | rebuild / patch base, pin digest, CI gate |

App-level ACL (роли guest/manager) — [ADR-005](../adr/ADR-005-security.md), не замена кластерному аудиту.

**Done-критерий lab:** для каждого High+ finding есть evidence, impact и конкретный building-шаг (даже если PR ещё не смержен).

---

## Vulnerability Management (внутренний сервис)

**Зачем:** сканер без процесса = PDF в никуда. VM — как findings доходят до fix и закрытия.

Жизненный цикл на отчётах из `tmp/sec-ops/`:

```text
discover → triage (severity + контекст) → ticket → fix/verify → close
```

| Severity | Ориентир triage |
|----------|-----------------|
| Critical | эксплуатируемо извне / cluster-admin / секреты в открытом Ingress |
| High | привилегии pod, отсутствие NetPol к Data plane, RCE-класс в образе при внешнем входе |
| Medium | hardening gaps без прямого пути |
| Low / Info | noise, informational CIS |

Сводка counts:

```bash
python scripts/sec/sec-parse-summary.py tmp/sec-ops
```

### Эскалация Senior / Lead

Самостоятельно закрываешь средние кейсы (нет NetPol, слабый securityContext, парсинг отчётов, ticket + fix-draft).  
Эскалируй, если:

- широкий `cluster-admin` / bind на default SA в «как бы prod»;
- признак RCE / remote code в образе или API при доступном Ingress;
- секреты в values при реальном внешнем доступе;
- неясный blast radius по etcd / hostPath / docker.sock;
- конфликт с владельцем платформы по срокам SLA.

---

## Отчёт для внутренних заказчиков + SOC

### Finding (бизнес + tech)

```text
Finding:     <что нашли>
Evidence:    <команда / файл / строка>
Impact:      <что значит для бизнеса / данных>
Likelihood:  <как реально достичь в этом контуре>
Fix:         <building: PR / Helm / policy>
Severity:    Critical | High | Medium | Low
Owner:       <платформа / app / security>
Status:      open | in progress | verified
```

Пример:

```text
Finding:     В namespace kp нет NetworkPolicy
Evidence:    kubectl -n kp get networkpolicy → No resources found
Impact:      Любой pod в кластере может ходить к postgres/neo4j/redis по ClusterIP;
             при компромиссе соседнего workload — доступ к данным Knowledge Platform
Fix:         NetworkPolicy default-deny + allow api→postgres, api→neo4j, …
Severity:    High
```

Клиентоориентированность: сначала **impact на процесс/данные**, потом CVE ID и флаги сканера. Не пугай «критикал» без контекста эксплуатации.

### IoC handoff → SOC / Blue Team

**Зачем:** после теста защитники должны знать, *что* искать в логах (IP, hash, URL, SA), а не перечитывать весь отчёт пентеста.

```text
indicator | type        | source finding      | first_seen | last_seen | confidence | blue_action
----------|-------------|---------------------|------------|-----------|------------|------------------
<ip/hash/url/sa> | ip/domain/hash/sa | sec-ops lab / ticket | ISO8601 | ISO8601 | high/med/low | block / watch / hunt
```

- **block** — блокировать индикатор; **watch** — алерт без автоблока; **hunt** — поиск по историческим логам.  
Передавай только индикаторы из **авторизованного** теста своего контура; уточняй false positive вместе с Blue Team.

---

## Red team / PoC (рамка)

| Элемент | В lab |
|---------|-------|
| Scope | namespace `kp`, `kp.local:8088`, локальный Docker Desktop |
| Critical assets | api, stores, Ingress, SA tokens |
| Цель упражнения | показать путь риска и приоритет fix |
| PoC | **narrative + evidence в отчёте**, не exploit payload в git |
| Metasploit / Kali | внешний toolchain на authorized engagement — не документируем шаги эксплуатации здесь |

На техсобесе удобная рамка: **misconfig → impact → fix**, без живого эксплойта.

---

## Zero-overlap: где что живёт

| Слой | Где |
|------|-----|
| Platform (api, stores, …) | Kubernetes `kp` |
| Ollama + Prometheus/Grafana/Jaeger | Compose `docker-compose.yml` |
| Trivy, Semgrep, Nmap, ZAP, Nuclei, kube-bench, Checkov | Compose `docker-compose.sec-ops.yml` (ephemeral) |

Сканеры **не** дублируют postgres/api и не держат долгоживущие контейнеры — только `compose run --rm`.

### Trivy: ERROR `[rego] … specify_ami_owners / requestedamis`

Это **не** finding по вашему chart. Старый Trivy качает свежий policy-bundle с AWS-проверками, которые он не понимает; check пропускается, скан Helm идёт дальше (`Detected config files`). В lab стоит образ `aquasec/trivy:0.61.1+`. Если логи всё ещё шумят — просто игнорируйте AWS `[rego]` строки.
