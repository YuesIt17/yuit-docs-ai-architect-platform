$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

# Docker Desktop Kubernetes (default) or kind (legacy):
#   $env:KP_K8S = "desktop"   # default
#   $env:KP_K8S = "kind"
$mode = if ($env:KP_K8S) { $env:KP_K8S.ToLowerInvariant() } else { "desktop" }

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
docker build -t kp-api:dev -f backend/Dockerfile .
docker build -t kp-frontend:dev frontend/

if ($mode -eq "kind") {
  $cluster = "retailpartnerx-kp"
  $exists = kind get clusters 2>$null | Select-String -Pattern "^$cluster$"
  if (-not $exists) {
    Write-Host "==> Creating kind cluster $cluster"
    kind create cluster --config infra/kind/kind-config.yaml
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

  # Local images are visible to Desktop K8s; Never avoids Hub pulls.
  $values = @("-f", "infra/helm/knowledge-platform/values-desktop.yaml")
}

$extra = @()
if ($env:KP_LLM -eq "ollama") {
  $extra += @("-f", "infra/helm/knowledge-platform/values-ollama.yaml")
}

Write-Host "==> Helm upgrade --install kp"
helm upgrade --install kp infra/helm/knowledge-platform `
  -n kp --create-namespace `
  @values `
  @extra `
  --wait --timeout 5m

Write-Host @"

Done (mode=$mode).
Add hosts: 127.0.0.1 kp.local

Docker Desktop:
  UI  http://kp.local:8088/          (LB; :80 often taken by IIS on Windows)
  API http://kp.local:8088/api/health
  Or: curl.exe -H "Host: kp.local" http://127.0.0.1:8088/api/health

kind (legacy):
  .\scripts\k8s-expose.ps1   -> http://kp.local:8088

For in-cluster Ollama: `$env:KP_LLM='ollama'; .\scripts\k8s-up.ps1
"@
