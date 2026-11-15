# Clean hybrid: Compose side-stack (Ollama + obs) + Desktop K8s platform (no service overlap).
# Real login with Keycloak and the BFF is the default. For the demo role switcher instead:
#   $env:KP_AUTH = "demo"; make demo
$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
Set-Location $Root

if (-not $env:KP_AUTH) { $env:KP_AUTH = "oidc" }

Write-Host "==> Compose side-stack (ollama + prometheus/grafana/tempo/loki)"
docker compose -f app/infra/docker-compose.yml --profile llm --profile obs up -d --remove-orphans
& "$Root\app\scripts\ollama\ollama-pull.ps1" -Model "qwen2.5:0.5b"

Write-Host "==> Kubernetes platform (api/frontend/stores/minio) + OLLAMA overlay, auth=$($env:KP_AUTH)"
$env:KP_LLM = "compose-ollama"
& "$Root\app\scripts\k8s\k8s-up.ps1"

if ($env:KP_AUTH -eq "oidc") {
  $ui = "http://kp.localhost:8088"
  $login = "  Login  users and passwords are in app/infra/helm/knowledge-platform/values-desktop-oidc.yaml"
} else {
  $ui = "http://kp.local:8088"
  $login = "  Login  none: pick a role in the UI (KP_AUTH=demo)"
}

Write-Host @"

Hybrid ready (Compose and Kubernetes run no duplicate services):
  UI     $ui
  API    $ui/api/health
$login
  Ollama http://127.0.0.1:11434/v1/models
  Graf   http://127.0.0.1:3000  (Explore: Tempo + Loki)
  Prom   http://127.0.0.1:9090
  Tempo  http://127.0.0.1:3200
  Loki   http://127.0.0.1:3100
"@
