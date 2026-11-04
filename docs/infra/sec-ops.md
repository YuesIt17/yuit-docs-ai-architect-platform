# DevSecOps / Security Engineer lab

The short path: **baseline → scanners → audit of your own `kp` → report (breaking) → fix (building)**.  
The goal is to practice Security Engineer duties on **this** platform (internal perimeter, Web/API, K8s, scanner orchestration, Vulnerability Management and SOC handoff) without attacking anyone else's systems.

Same style as [SRE.md](../SRE.md): ready-to-run commands, minimal theory.

| What this is | What this is not |
|---------|------------|
| An authorized audit of **your own** local cluster / `kp.local` | A guide to breaking into other people's systems |
| Scanners + `kubectl` + report / IoC templates | Step-by-step Metasploit / ready-made exploit PoCs |
| Breaking **and** building (misconfig → impact → Helm/fix) | Just finding a CVE and walking away |
| Cluster and supply-chain security | App ACL / guardrails ([ADR-005](../../architecture/adr/ADR-005-security.md)) |

Infrastructure: [compose-dev.md](compose-dev.md) · [k8s-architecture.md](k8s-architecture.md) · scanner Compose file: [`app/infra/docker-compose.sec-ops.yml`](../../app/infra/docker-compose.sec-ops.yml).

**OS:** **Windows (PowerShell)** and **macOS (zsh/bash)** blocks. `make` works on both if GNU Make is installed.

---

## Duty map → this lab

| Duty / skill (JD) | In this lab | Outside the lab (job / separate environment) |
|--------------------------|------------|-------------------------------------|
| Automated + manual pentest (internal perimeter, Web, API, segments) | Nmap, ZAP, Nuclei, Semgrep, kubectl; manual UI/API walkthrough | Burp Suite, Nessus, full red-team scope |
| Cloud (OpenStack) and container (K8s) audit | K8s: RBAC, NetPol, PSS, Trivy, kube-bench, Checkov | OpenStack: checklist below (no environment in the repo) |
| PoC / risk demonstration to the business | Report: evidence → impact → fix (business language) | Live exploit PoC: **not** in this repo |
| Red team exercises (critical assets) | Scenario frame on `kp` assets | Kali/Parrot + Metasploit on an authorized engagement |
| Scanner orchestration (Python/Bash) + JSON parsing | `make sec-scan`, `sec-parse-*.py` | Burp Enterprise / Nessus API at work |
| K8s hardening (RBAC, NetPol, PSS / Gatekeeper, admission) | Checklist + building fixes; Checkov/Trivy config | OPA Gatekeeper / Kyverno in a shared/prod cluster |
| Vulnerability Management as a service | Lifecycle on `tmp/sec-ops/` | Jira/ServiceNow + company SLA |
| SOC / Blue Team handoff (IoC) | IoC template below | Real SIEM / ticketing |
| Kali / Parrot, Burp, Metasploit, Nmap | Nmap (+ ZAP) in Compose; the rest is an external toolchain | Installing Kali/Burp/msf on a host |
| Python / Bash automation | `app/scripts/sec/sec-scan.*` scripts, parse helpers | Extending orchestration to corporate scanners |
| K8s architecture (etcd, apiserver, CNI) | Baseline below + namespace audit | Control-plane deep dive on bare metal/cloud |
| Breaking ↔ building | Findings table + Helm fix direction | PR with the platform's customer |
| Customer focus | Report template for internal customers | Stakeholder meetings |
| Autonomy + escalation | Medium findings handled alone; Senior/Lead escalation criteria | — |

---

## Rules and scope

1. Scan only **your own** Docker Desktop / kind and namespace `kp`.
2. Nmap / ZAP / Nuclei: only `127.0.0.1`, `kp.local`, `host.docker.internal` (from a container). Never point scanners at other networks or other people's IPs.
3. The findings below are for learning (desktop chart), not a company production hardening checklist.
4. A finding without a **building** recommendation counts as an unfinished lab step.
5. The repository contains **no** ready-made exploit PoCs or Metasploit modules: risk is shown through a report and a fix.

From Compose containers, the Ingress target is **`http://host.docker.internal:8088`** (in a browser on the host, `http://kp.local:8088`).

---

## Glossary (lab terms)

| Term | What it is | Why a Security Engineer cares |
|--------|---------|-------------------------|
| **DevSecOps** | Security built into development and delivery (scan → fix → CI), not a department at the end | The lab's role: catch misconfigs/CVEs before production |
| **internal perimeter** | Networks/services inside a company or local environment, not the public internet | Typical pentest / audit scope |
| **kp / `kp.local`** | Namespace and hostname of our Knowledge Platform | The only allowed scanner target for this lab |
| **finding** | A specific discovery (misconfig, CVE, open port) with evidence | The unit of reporting and triage |
| **breaking / building** | Find or break a risk → propose and make the fix | The full Security Engineer cycle, not just finding things |
| **misconfig** | An insecure setting (no NetPol, privileged, secrets in values) | More often a real risk than a bare CVE |
| **PoC** | Proof of Concept: a demonstration that a risk is real | Here: narrative + evidence in the report, no exploit in git |
| **RBAC** | Role-Based Access Control: who can do what through the API | Audit of `can-i`, ClusterRoleBinding, SA |
| **SA** | ServiceAccount: a Pod's identity in the API | A stolen token + broad rights = a path to Secrets |
| **NetPol** | NetworkPolicy: a pod↔pod firewall | Without it the network is flat: any pod → postgres |
| **PSS** | Pod Security Standards (Privileged / Baseline / Restricted) | Policy on which Pods can be created at all |
| **Admission** | Controllers that check an object **before** create/update | Gatekeeper / Kyverno / PSS block privileged, hostPath |
| **OPA Gatekeeper / Kyverno** | Policy engines in the cluster (rules as code) | Not installed in the lab; a direction for production |
| **CNI** | Container Network Interface: how Pods get IPs and routes | The basis for segmentation; NetPol works on top of the CNI |
| **CIS** | Center for Internet Security: benchmarks for how things should be | kube-bench checks CIS Kubernetes |
| **CVE** | A known software vulnerability (numbered in a database) | Trivy finds CVEs in images; triage by severity + context |
| **IaC** | Infrastructure as Code (Helm, Terraform, manifests) | Checkov / Trivy config: YAML policies before deployment |
| **supply-chain** | The chain of builds, images and dependencies | Image scan + pinned digest + CI gate |
| **Vulnerability Management** | A process: find → assess → ticket → fix → verify | A service, not a one-off scanner report |
| **triage** | Review: false positive? severity? fix priority? | Without triage, a scanner is noise |
| **SOC / Blue Team** | Monitoring center / defenders (detection, response) | They receive the IoCs after a test |
| **IoC** | Indicator of Compromise: IP, hash, URL, SA for hunting/blocking | Handoff template below |
| **SIEM** | A log and alert collection system (at work) | Outside the lab; only the IoC format here |
| **IMDS** | Instance Metadata Service in the cloud (credentials from a VM) | Analogous risk: SA token / cloud metadata from a pod |
| **blast radius** | How far a compromise spreads | etcd / hostPath / docker.sock → nearly the whole cluster |
| **ephemeral** | A scanner container lives only for the `compose run` | Holds no DB/API; does not overlap with `kp` |
| **FOSS** | Free/Open Source Software | ZAP is the free alternative to Burp in the lab |
| **RCE** | Remote Code Execution | A critical class; escalate to Senior/Lead |
| **JD** | Job Description: the requirements of a vacancy | The "duty" column in the map above |

K8s objects (Pod, Deployment, Secret, Ingress…): [k8s-primer.md](k8s-primer.md).

---

## Competency baseline

### Kubernetes (control plane and attack path)

| Component | What it is | Why a Security Engineer cares |
|-----------|---------|-------------------------|
| **kube-apiserver** | The cluster's API gateway | Single authn/authz point; all `kubectl` and controllers go through it |
| **etcd** | Key-value state store | Secrets and config at rest; access to etcd ≈ full compromise |
| **kubelet** | Agent on each Node that runs containers | Weak kubelet API / privileged pod → escape to the host |
| **CNI** | Pod network plugin | Without NetworkPolicy the network is flat (any pod → any pod) |
| **RBAC** | Roles and bindings to users/SAs | Who can do what through the API |
| **Admission** | Hooks before create (PSS / Gatekeeper / Kyverno) | Block unsafe Pods before they reach the cluster |

Risk path to remember: `Pod → SA token → RBAC → Secrets / privileged → Node`.

Objects to audit: Pod, Deployment, ServiceAccount, Secret, Service, Ingress, Namespace, NetworkPolicy.

Commands: `kubectl get`, `describe`, `auth can-i`.

### Shell (Bash / PowerShell) and Python

| Skill | Windows | macOS |
|-------|---------|-------|
| YAML search | `Select-String` | `grep -E` |
| Scanners | `docker compose run --rm` | same |
| Reports | `tmp\sec-ops\` | `tmp/sec-ops/` |
| JSON parsing | `python app/scripts/sec/sec-parse-trivy.py` · `sec-parse-summary.py` | same |

### Toolchain matrix (what each tool does)

Layers: **image** → **code** → **IaC/Helm** → **cluster (CIS/RBAC)** → **network/ports** → **Web/API**. No single scanner covers everything.

| Tool | What it does | Why in the lab / at work | In the lab |
|------------|------------|-------------------------|-------|
| **Trivy** | CVEs in Docker images + basic misconfigs in YAML/Helm | What is dangerous in `kp-api:dev` and the chart? | compose |
| **Semgrep** | Static code analysis (SAST rules) | Find typical security bugs in `app/backend/` without running it | compose |
| **Checkov** | Policy-as-code for IaC (Helm/K8s) | Does the chart violate best practices? (complements Trivy config) | compose |
| **Nmap** | Port and service version scan | What the host listens on: Ingress 8088 and anything extra | compose → `host.docker.internal` |
| **Nuclei** | Templates for known web/API vulnerabilities | Quick automatic HTTP check of `kp.local` for known patterns | compose |
| **OWASP ZAP** | Automated/passive web scanner (proxy) | FOSS alternative to Burp: UI/API baseline | compose; `SEC_SCAN_DEEP=1` |
| **kube-bench** | CIS Kubernetes checks | Control-plane/node/policy hardening | compose; often skipped on Desktop |
| **Burp Suite** | Manual proxy for Web/API (Repeater, Intruder…) | Deep manual audit at work | external → `http://kp.local:8088` |
| **Nessus** | Enterprise infrastructure vulnerability scanner | Broad infra scan; replaced by Trivy+Nmap+Checkov in the lab | external |
| **Kali / Parrot** | Distributions with a pentest toolchain | Ready environment (Nmap, Burp, msf…) | external host |
| **Metasploit** | Exploitation framework | Authorized red team only; **this doc has no exploit steps** | external |

---

## OpenStack (concept, no environment in the repo)

**Why this section:** job descriptions often list OpenStack audits. There is no environment in the repo, so below is a mapping from cloud to the same skill on `kp`.

| Area | What it is / what to check | Equivalent in `kp` / K8s |
|---------|--------------------|---------------------|
| Identity / RBAC | who is a cloud admin, excess roles | K8s RBAC, SA bindings |
| Security groups | VM firewall: open `0.0.0.0/0`, excess ports | NetworkPolicy, Ingress |
| Metadata / IMDS | An HTTP service on the VM hands out cloud credentials | SA tokens in a pod, cloud metadata |
| Images / volumes | outdated VM images, public disks | Trivy image, registry policy |
| Tenant vs provider net | tenant network isolation | CNI + NetPol |
| Logging / audit | who changed SGs / roles | Kubernetes audit logs, SIEM |

This repository does **not** bring up OpenStack; this is only a checklist for transferring skills.

---

## Prerequisites

Required: Docker Desktop (or kind), `kubectl`, `helm`, `docker`. The `kp-api:dev` / `kp-frontend:dev` images are built in `k8s-up`.

**Windows**

```powershell
make demo
# or: .\app\scripts\hybrid\hybrid-up.ps1
# or cluster only: .\app\scripts\k8s\k8s-up.ps1
kubectl -n kp get pods
```

**macOS**

```bash
make demo
# or: bash app/scripts/hybrid/hybrid-up.sh
# or cluster only: bash app/scripts/k8s/k8s-up.sh
kubectl -n kp get pods
```

---

## Quick start (single pass)

Scripts: [`sec-scan.ps1`](../../app/scripts/sec/sec-scan.ps1) (Windows) · [`sec-scan.sh`](../../app/scripts/sec/sec-scan.sh) (macOS).

| Step | Result |
|-----|-----------|
| kubectl checklist | `tmp/sec-ops/kubectl-audit.txt` |
| Trivy images + Helm config | `tmp/sec-ops/trivy-*.json` (+ parse) |
| Semgrep `app/backend/` | `tmp/sec-ops/semgrep.json` |
| Checkov (Helm) | `tmp/sec-ops/checkov.json` |
| Nmap (localhost Ingress) | `tmp/sec-ops/nmap.txt` |
| Nuclei | `tmp/sec-ops/nuclei.txt` |
| kube-bench (best-effort) | `tmp/sec-ops/kube-bench.txt` or skip |
| ZAP baseline | only with `SEC_SCAN_DEEP=1` → `tmp/sec-ops/zap-baseline.*` |
| Count summary | stdout from `sec-parse-summary.py` |

**Windows**

```powershell
make sec-scan
# or: .\app\scripts\sec\sec-scan.ps1

# deep pass (+ ZAP; takes longer):
$env:SEC_SCAN_DEEP = "1"; make sec-scan
```

**macOS**

```bash
make sec-scan
# or: bash app/scripts/sec/sec-scan.sh

# deep pass (+ ZAP; takes longer):
SEC_SCAN_DEEP=1 make sec-scan
```

Reports go to `tmp/sec-ops/` (not committed to git).

### Manually (basic scanners)

**Windows / macOS** (the Compose lines are identical)

```bash
docker compose -f app/infra/docker-compose.sec-ops.yml run --rm trivy image --severity HIGH,CRITICAL kp-api:dev
docker compose -f app/infra/docker-compose.sec-ops.yml run --rm semgrep semgrep --config=auto /src/backend
docker compose -f app/infra/docker-compose.sec-ops.yml run --rm checkov -d /src/infra/helm/knowledge-platform --framework kubernetes helm --soft-fail -o json --output-file-path /out
docker compose -f app/infra/docker-compose.sec-ops.yml run --rm nmap -sV -p 8088,80,443 -oN /out/nmap.txt host.docker.internal
docker compose -f app/infra/docker-compose.sec-ops.yml run --rm nuclei -u http://host.docker.internal:8088 -silent -o /out/nuclei.txt
```

ZAP (deep):

```bash
docker compose -f app/infra/docker-compose.sec-ops.yml run --rm zap \
  zap-baseline.py -t http://host.docker.internal:8088 -J /out/zap-baseline.json -I
```

---

## Lab on `kp`

Each step covers one layer of defense. The goal is to collect findings with evidence, not to run every flag.

### 1. Namespace reconnaissance + control plane sanity check

**Why:** understand the attack surface: what is running, whether NetPol/Ingress/Secrets exist, and whether `cluster-admin` is being handed out.

**Windows**

```powershell
kubectl -n kp get deploy,svc,ingress,sa,secret,networkpolicy
kubectl -n kp get pods -o wide
kubectl get clusterrolebinding -o wide | Select-String "kp|cluster-admin"
kubectl get --raw='/readyz?verbose'   # apiserver health (if available)
```

**macOS**

```bash
kubectl -n kp get deploy,svc,ingress,sa,secret,networkpolicy
kubectl -n kp get pods -o wide
kubectl get clusterrolebinding -o wide | grep -E "kp|cluster-admin"
kubectl get --raw='/readyz?verbose'   # apiserver health (if available)
```

Record: how many Deployments, whether there is an Ingress or NetworkPolicy, which Secrets and SAs exist.

Critical assets for the red-team frame: Ingress `kp.local`, `deploy/api`, postgres / neo4j / redis / qdrant / minio (Data plane).

### 2. Misconfigurations (privileged / host / RBAC)

**Why:** the typical K8s compromise path is privileged/hostPath/docker.sock and excessively broad default SA rights.

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

### 3. Trivy: images and manifests

**Why:** CVEs in `kp-api` / `kp-frontend` and gross errors in Helm YAML (supply chain + config).

```bash
docker compose -f app/infra/docker-compose.sec-ops.yml run --rm trivy image -f json -o /out/trivy-api.json kp-api:dev
docker compose -f app/infra/docker-compose.sec-ops.yml run --rm trivy image -f json -o /out/trivy-frontend.json kp-frontend:dev
docker compose -f app/infra/docker-compose.sec-ops.yml run --rm trivy config /src/infra/helm/knowledge-platform
python app/scripts/sec/sec-parse-trivy.py tmp/sec-ops/trivy-api.json
```

### 4. Semgrep: backend code

**Why:** SAST finds patterns such as unsafe SQL, deserialization or secrets in code before deployment.

**Windows**

```powershell
docker compose -f app/infra/docker-compose.sec-ops.yml run --rm semgrep `
  semgrep --config=auto --json -o /out/semgrep.json /src/backend
```

**macOS**

```bash
docker compose -f app/infra/docker-compose.sec-ops.yml run --rm semgrep \
  semgrep --config=auto --json -o /out/semgrep.json /src/backend
```

Optional: `/src/frontend` with the same service.

### 5. Checkov — IaC / Helm policy

**Why:** policy-as-code for the chart: missing securityContext, excess capabilities, public Services and so on.

```bash
docker compose -f app/infra/docker-compose.sec-ops.yml run --rm checkov \
  -d /src/infra/helm/knowledge-platform \
  --framework kubernetes helm --soft-fail \
  -o json --output-file-path /out
# report: tmp/sec-ops/results_json.json (the script renames it to checkov.json)
```

### 6. Nmap: segment / open ports (localhost only)

**Why:** from the outside, only what the host listens on is visible; an extra open port is extra attack surface.

```bash
docker compose -f app/infra/docker-compose.sec-ops.yml run --rm nmap \
  -sV -p 8088,80,443,11434 -oN /out/nmap.txt host.docker.internal
```

On the host, you can compare with `http://kp.local:8088`. Do not scan other subnets.

### 7. Nuclei — web/API templates

**Why:** a quick run of known HTTP/API checks (headers, path disclosure, typical misconfigs) against the Ingress.

```bash
docker compose -f app/infra/docker-compose.sec-ops.yml run --rm nuclei \
  -u http://host.docker.internal:8088 -silent -o /out/nuclei.txt
```

### 8. OWASP ZAP: baseline (FOSS alternative to Burp)

**Why:** a passive/basic web audit of the UI and API (like a simplified Burp without a manual proxy).  
A slow step; in `make sec-scan` it runs only with `SEC_SCAN_DEEP=1`.

```bash
docker compose -f app/infra/docker-compose.sec-ops.yml run --rm zap \
  zap-baseline.py -t http://host.docker.internal:8088 -J /out/zap-baseline.json -I
```

The manual equivalent at work: Burp Suite against the same URL, using **Proxy** (traffic interception), **Repeater** (replay/edit a request) and **Intruder** (parameter enumeration), and only as the engagement policy allows.

### 9. kube-bench — CIS (best-effort)

**Why:** compare the cluster with CIS Kubernetes (etcd encryption, anon-auth, node files…). Often skipped on Desktop because the node filesystem is unavailable.  
On kind or a VM with node access:

```bash
docker compose -f app/infra/docker-compose.sec-ops.yml run --rm kube-bench \
  run --targets policies 2>&1 | tee tmp/sec-ops/kube-bench.txt
```

Alternative in the cluster: the Job from the Aqua kube-bench documentation (not part of Compose).

### 10. Hardening direction (building)

**Why:** close breaking findings with concrete controls (NetPol, PSS, RBAC, admission, image gate).  
In the desktop lab, Gatekeeper is usually **not** installed (too heavy for a laptop). The direction for production / shared clusters:

| Control | What to do |
|----------|-------------|
| NetworkPolicy | default-deny Ingress/Egress + allowlist api→stores |
| Pod Security | `securityContext`: `runAsNonRoot`, drop `ALL`, `readOnlyRootFilesystem`; namespace PSS Restricted |
| RBAC | separate SA per workload, minimal Role, not the default SA |
| Admission | OPA Gatekeeper / Kyverno: ban privileged, hostPath, `:latest` |
| Images | Trivy in CI; do not deploy CRITICAL without an exception |

Example NetworkPolicy idea (not applied automatically; a building draft):

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

Next, add separate allow rules for `api → postgres/neo4j/redis/...` and Ingress controller → app/frontend/api.

---

## Breaking ↔ Building (typical findings on this chart)

| Observation | Why it is this way in the MVP | Building fix |
|------------|------------------|--------------|
| No `NetworkPolicy` | Desktop demo, flat CNI | default-deny + allowlist |
| Passwords/DSN in env values | Simple Helm for a laptop | Secret / External Secrets / Vault |
| Weak or missing `securityContext` | Not PSS Restricted | `runAsNonRoot`, drop caps, readOnlyRootFilesystem |
| Exposed Ingress (`kp.local`) | The demo needs a UI | Auth at the edge; do not expose extra NodePorts |
| Default SA on pods | Chart has no separate SAs | separate SA + minimal Role |
| CRITICAL/HIGH CVEs in images | Base image | rebuild / patch base, pin digest, CI gate |

App-level ACL (guest/manager roles) is covered in [ADR-005](../../architecture/adr/ADR-005-security.md) and does not replace a cluster audit.

**Lab done criterion:** every High+ finding has evidence, impact and a concrete building step (even if the PR is not merged yet).

---

## Vulnerability Management (internal service)

**Why:** a scanner without a process is a PDF nobody reads. VM is how findings reach a fix and closure.

Lifecycle on reports from `tmp/sec-ops/`:

```text
discover → triage (severity + context) → ticket → fix/verify → close
```

| Severity | Triage guide |
|----------|-----------------|
| Critical | exploitable from outside / cluster-admin / secrets on an open Ingress |
| High | pod privileges, no NetPol to the Data plane, RCE class in an image with external entry |
| Medium | hardening gaps without a direct path |
| Low / Info | noise, informational CIS |

Count summary:

```bash
python app/scripts/sec/sec-parse-summary.py tmp/sec-ops
```

### Senior / Lead escalation

Close medium cases on your own (no NetPol, weak securityContext, report parsing, ticket + fix draft).  
Escalate if:

- there is a broad `cluster-admin` / binding on the default SA in a production-like environment;
- there are signs of RCE / remote code in an image or API with an accessible Ingress;
- secrets are in values with real external access;
- the blast radius through etcd / hostPath / docker.sock is unclear;
- SLA deadlines conflict with the platform owner.

---

## Report for internal customers + SOC

### Finding (business + tech)

```text
Finding:     <what was found>
Evidence:    <command / file / line>
Impact:      <what it means for the business / data>
Likelihood:  <how realistically it can be reached in this perimeter>
Fix:         <building: PR / Helm / policy>
Severity:    Critical | High | Medium | Low
Owner:       <platform / app / security>
Status:      open | in progress | verified
```

Example:

```text
Finding:     Namespace kp has no NetworkPolicy
Evidence:    kubectl -n kp get networkpolicy → No resources found
Impact:      Any pod in the cluster can reach postgres/neo4j/redis over ClusterIP;
             if a neighboring workload is compromised, Knowledge Platform data is exposed
Fix:         NetworkPolicy default-deny + allow api→postgres, api→neo4j, …
Severity:    High
```

Customer focus: lead with the **impact on the process/data**, then the CVE ID and scanner flags. Do not raise alarm with "critical" without exploitation context.

### IoC handoff → SOC / Blue Team

**Why:** after a test, defenders need to know *what* to look for in logs (IP, hash, URL, SA) without rereading the whole pentest report.

```text
indicator | type        | source finding      | first_seen | last_seen | confidence | blue_action
----------|-------------|---------------------|------------|-----------|------------|------------------
<ip/hash/url/sa> | ip/domain/hash/sa | sec-ops lab / ticket | ISO8601 | ISO8601 | high/med/low | block / watch / hunt
```

- **block**: block the indicator; **watch**: alert without auto-blocking; **hunt**: search historical logs.  
Hand over only indicators from an **authorized** test of your own perimeter; confirm false positives with the Blue Team.

---

## Red team / PoC (frame)

| Element | In the lab |
|---------|-------|
| Scope | namespace `kp`, `kp.local:8088`, local Docker Desktop |
| Critical assets | api, stores, Ingress, SA tokens |
| Exercise goal | show the risk path and fix priority |
| PoC | **narrative + evidence in the report**, no exploit payload in git |
| Metasploit / Kali | external toolchain on an authorized engagement; exploitation steps are not documented here |

A convenient frame for technical discussions: **misconfig → impact → fix**, with no live exploit.

---

## Zero-overlap: where everything lives

| Layer | Where |
|------|-----|
| Platform (api, stores, …) | Kubernetes `kp` |
| Ollama + Prometheus/Grafana/Loki/Tempo | Compose `docker-compose.yml` |
| Trivy, Semgrep, Nmap, ZAP, Nuclei, kube-bench, Checkov | Compose `docker-compose.sec-ops.yml` (ephemeral) |

Scanners do **not** duplicate postgres/api and do not hold long-lived containers; they use only `compose run --rm`.

### Trivy: ERROR `[rego] … specify_ami_owners / requestedamis`

This is **not** a finding about your chart. An old Trivy downloads a fresh policy bundle with AWS checks it does not understand; the check is skipped and the Helm scan continues (`Detected config files`). The lab uses the `aquasec/trivy:0.61.1+` image. If the logs are still noisy, ignore the AWS `[rego]` lines.
