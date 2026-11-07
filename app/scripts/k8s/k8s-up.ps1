$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
Set-Location $Root

# Docker Desktop Kubernetes (default) or kind (legacy):
#   $env:KP_K8S = "desktop"   # default
#   $env:KP_K8S = "kind"
# Real login with Keycloak and the BFF, on Docker Desktop only:
#   $env:KP_AUTH = "oidc"
$mode = if ($env:KP_K8S) { $env:KP_K8S.ToLowerInvariant() } else { "desktop" }
$auth = if ($env:KP_AUTH) { $env:KP_AUTH.ToLowerInvariant() } else { "demo" }
if ($auth -eq "oidc" -and $mode -eq "kind") {
  throw "KP_AUTH=oidc is set up for Docker Desktop only (values-desktop-oidc.yaml)."
}

Write-Host "==> Checking tools"
foreach ($cmd in @("helm", "kubectl", "docker")) {
  if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) {
    throw "Missing required command: $cmd"
  }
}
if ($mode -eq "kind" -and -not (Get-Command kind -ErrorAction SilentlyContinue)) {
  throw "Missing required command: kind (or set KP_K8S=desktop)"
}

Write-Host "==> Building images"
docker build -t kp-api:dev -f app/backend/Dockerfile .
docker build -t kp-frontend:dev app/frontend/
if ($auth -eq "oidc") {
  docker build -t kp-bff:dev app/bff/
  if ($LASTEXITCODE -ne 0) { throw "docker build kp-bff failed" }
  docker build -t kp-keycloak:dev app/infra/keycloak/
  if ($LASTEXITCODE -ne 0) { throw "docker build kp-keycloak failed" }
}

if ($mode -eq "kind") {
  $cluster = "retailpartnerx-kp"
  $exists = kind get clusters 2>$null | Select-String -Pattern "^$cluster$"
  if (-not $exists) {
    Write-Host "==> Creating kind cluster $cluster"
    kind create cluster --config app/infra/kind/kind-config.yaml
  } else {
    Write-Host "==> kind cluster $cluster already exists"
  }

  Write-Host "==> Ensuring ingress-nginx (kind)"
  kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml
  kubectl label node "$cluster-control-plane" ingress-ready=true --overwrite | Out-Null
  kubectl -n ingress-nginx patch deployment ingress-nginx-controller --type merge -p '{"spec":{"template":{"spec":{"nodeSelector":{"kubernetes.io/os":"linux","ingress-ready":"true"}}}}}'
  kubectl wait --namespace ingress-nginx --for=condition=ready pod --selector=app.kubernetes.io/component=controller --timeout=180s

  Write-Host "==> Loading images into kind"
  kind load docker-image kp-api:dev kp-frontend:dev --name $cluster
  docker image inspect bitnamilegacy/minio:2025.7.23-debian-12-r5 2>$null | Out-Null
  if ($LASTEXITCODE -eq 0) {
    kind load docker-image bitnamilegacy/minio:2025.7.23-debian-12-r5 --name $cluster
  }

  $values = @()
} else {
  Write-Host "==> Using Docker Desktop Kubernetes context"
  kubectl config use-context docker-desktop | Out-Null
  $nodes = kubectl get nodes --request-timeout=10s 2>&1
  if ($LASTEXITCODE -ne 0) {
    throw "docker-desktop context not ready. Enable Kubernetes in Docker Desktop Settings.`n$nodes"
  }

  Write-Host "==> Ensuring ingress-nginx (LoadBalancer -> localhost)"
  helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx 2>$null | Out-Null
  helm repo update ingress-nginx | Out-Null
  helm upgrade --install ingress-nginx ingress-nginx/ingress-nginx `
    --namespace ingress-nginx --create-namespace `
    --set controller.service.type=LoadBalancer `
    --set controller.service.ports.http=8088 `
    --set controller.service.ports.https=8443 `
    --wait --timeout 5m

  # Docker Desktop can run Kubernetes as a kind cluster named "desktop". Its node does not see images built
  # with `docker build`, so pods would fail with ErrImageNeverPull until the images are loaded.
  $kindClusters = if (Get-Command kind -ErrorAction SilentlyContinue) { kind get clusters 2>$null } else { @() }
  if ($kindClusters -contains "desktop") {
    $images = @("kp-api:dev", "kp-frontend:dev")
    if ($auth -eq "oidc") { $images += @("kp-bff:dev", "kp-keycloak:dev") }
    Write-Host "==> Loading local images into the Docker Desktop kind node (takes a few minutes)"
    kind load docker-image @images --name desktop
    if ($LASTEXITCODE -ne 0) { throw "kind load failed" }
  } elseif ((docker ps --format "{{.Names}}") -contains "desktop-control-plane") {
    Write-Warning "Docker Desktop runs Kubernetes with kind, but the kind CLI is missing. Install it, or pods fail with ErrImageNeverPull."
  }

  $values = @("-f", "app/infra/helm/knowledge-platform/values-desktop.yaml")
}

$extra = @()
if ($auth -eq "oidc") {
  $extra += @("-f", "app/infra/helm/knowledge-platform/values-desktop-oidc.yaml")
}
if ($env:KP_LLM -eq "compose-ollama") {
  $extra += @("-f", "app/infra/helm/knowledge-platform/values-desktop-compose-ollama.yaml")
} elseif ($env:KP_LLM -eq "ollama") {
  Write-Warning "KP_LLM=ollama (in-cluster) removed. Use compose-ollama + make llm-ollama."
  $extra += @("-f", "app/infra/helm/knowledge-platform/values-desktop-compose-ollama.yaml")
}

# Avoid SSA conflict when something else (e.g. kubectl scale / HPA remnant) owns .spec.replicas
if (kubectl -n kp get deploy api -o name 2>$null) {
  Write-Host "==> Align api replicas to chart (1) before Helm apply"
  kubectl -n kp scale deploy/api --replicas=1 2>$null | Out-Null
}

Write-Host "==> Helm upgrade --install kp"
helm upgrade --install kp app/infra/helm/knowledge-platform `
  -n kp --create-namespace `
  @values `
  @extra `
  --wait --timeout 5m

# Mutable tags (kp-*:dev) + imagePullPolicy Never: Helm spec unchanged → pods keep old digest.
# Force recreate so Docker Desktop / kind pick up the images we just built.
Write-Host "==> Rollout restart api/frontend (pick up rebuilt :dev images)"
kubectl -n kp rollout restart deploy/api deploy/frontend
kubectl -n kp rollout status deploy/api --timeout=120s
kubectl -n kp rollout status deploy/frontend --timeout=120s
if ($auth -eq "oidc") {
  kubectl -n kp rollout restart deploy/bff
  kubectl -n kp rollout status deploy/bff --timeout=120s
  Write-Host @"

Done (mode=$mode, auth=oidc). No hosts entry is needed: browsers resolve *.localhost themselves.
  UI  http://kp.localhost:8088/
  Demo users are in app/infra/helm/knowledge-platform/values-desktop-oidc.yaml
  Check: python app/scripts/k8s/oidc_e2e.py
"@
  exit 0
}

Write-Host @"

Done (mode=$mode).
Add hosts: 127.0.0.1 kp.local

Docker Desktop:
  UI  http://kp.local:8088/          (LB; :80 often taken by IIS on Windows)
  API http://kp.local:8088/api/health
  Or: curl.exe -H "Host: kp.local" http://127.0.0.1:8088/api/health

Hybrid LLM: make llm-ollama; then `$env:KP_LLM='compose-ollama'; .\app\scripts\k8s\k8s-up.ps1
Observability: make obs  (Prometheus / Grafana / Loki / Tempo — Compose only)
"@
