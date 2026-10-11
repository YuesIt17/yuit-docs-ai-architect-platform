# DevSecOps lab: kubectl audit + Trivy images + Semgrep on backend.
# Requires: docker, kubectl. Prefer after `make demo` / `make k8s-up`.
# Docs: docs/infra/sec-ops.md

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Compose = "infra/docker-compose.sec-ops.yml"
$OutDir = Join-Path $Root "tmp\sec-ops"
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

Write-Host "==> kubectl audit (namespace kp)"
$audit = Join-Path $OutDir "kubectl-audit.txt"
$lines = New-Object System.Collections.Generic.List[string]
$lines.Add("=== kubectl audit $(Get-Date -Format o) ===")
$lines.Add("")

function Invoke-KubectlCapture([string[]]$KubectlArgs) {
  $cmd = "kubectl " + ($KubectlArgs -join " ")
  $lines.Add("`$ $cmd")
  try {
    $out = & kubectl @KubectlArgs 2>&1 | Out-String
    $lines.Add($out.TrimEnd())
  } catch {
    $lines.Add("(kubectl failed: $($_.Exception.Message))")
  }
  $lines.Add("")
}

if (Get-Command kubectl -ErrorAction SilentlyContinue) {
  Invoke-KubectlCapture @("-n", "kp", "get", "deploy,svc,ingress,sa,secret,networkpolicy")
  Invoke-KubectlCapture @("-n", "kp", "get", "pods", "-o", "wide")
  Invoke-KubectlCapture @("auth", "can-i", "--list", "--as=system:serviceaccount:kp:default", "-n", "kp")
  Invoke-KubectlCapture @("auth", "can-i", "get", "secrets", "--as=system:serviceaccount:kp:default", "-n", "kp")
  Invoke-KubectlCapture @("auth", "can-i", "create", "pods", "--as=system:serviceaccount:kp:default", "-n", "kp")

  $lines.Add("`$ kubectl -n kp get pods -o yaml | Select-String privileged|hostNetwork|hostPath|docker.sock")
  try {
    $yaml = kubectl -n kp get pods -o yaml 2>&1 | Out-String
    $hits = $yaml | Select-String -Pattern "privileged:|hostNetwork:|hostPath:|docker.sock" -AllMatches
    if ($hits) {
      $lines.Add(($hits | ForEach-Object { $_.Line.Trim() } | Select-Object -Unique) -join "`n")
    } else {
      $lines.Add("(no matches for privileged/hostNetwork/hostPath/docker.sock)")
    }
  } catch {
    $lines.Add("(pod yaml scan failed - is namespace kp up?)")
  }
  $lines.Add("")
} else {
  $lines.Add("kubectl not found - skip cluster audit")
  Write-Host "WARN: kubectl not found; skipping cluster audit" -ForegroundColor Yellow
}

$lines | Set-Content -Path $audit -Encoding utf8
Write-Host "    wrote $audit"

Write-Host "==> Trivy image scans"
$images = @("kp-api:dev", "kp-frontend:dev")
foreach ($img in $images) {
  $safe = $img -replace "[:/]", "-"
  $jsonOut = "/out/trivy-$safe.json"
  Write-Host "    scanning $img"
  docker compose -f $Compose run --rm trivy image --severity HIGH,CRITICAL -f json -o $jsonOut $img
  if ($LASTEXITCODE -ne 0 -and $LASTEXITCODE -ne 1) {
    Write-Host "WARN: trivy exit $LASTEXITCODE for $img (image missing? build via make k8s-up)" -ForegroundColor Yellow
  }
}

Write-Host "==> Trivy config (Helm chart)"
docker compose -f $Compose run --rm trivy config -f json -o /out/trivy-helm-config.json /src/infra/helm/knowledge-platform
if ($LASTEXITCODE -ne 0 -and $LASTEXITCODE -ne 1) {
  Write-Host "WARN: trivy config exit $LASTEXITCODE" -ForegroundColor Yellow
}

Write-Host "==> Parse Trivy CRITICAL/HIGH"
$trivyFiles = Get-ChildItem -Path $OutDir -Filter "trivy-*.json" -ErrorAction SilentlyContinue
if ($trivyFiles) {
  python (Join-Path $Root "scripts\sec-parse-trivy.py") @($trivyFiles.FullName)
} else {
  Write-Host "WARN: no trivy JSON reports" -ForegroundColor Yellow
}

Write-Host "==> Semgrep backend"
docker compose -f $Compose run --rm semgrep `
  semgrep --config=auto --quiet --json -o /out/semgrep.json /src/backend
if ($LASTEXITCODE -ne 0 -and $LASTEXITCODE -ne 1) {
  Write-Host "WARN: semgrep exit $LASTEXITCODE" -ForegroundColor Yellow
} else {
  $sg = Join-Path $OutDir "semgrep.json"
  if (Test-Path $sg) {
    try {
      $data = Get-Content $sg -Raw | ConvertFrom-Json
      $n = @($data.results).Count
      Write-Host "    semgrep findings: $n  ($sg)"
    } catch {
      Write-Host "    wrote $sg"
    }
  }
}

Write-Host ""
Write-Host "Done. Reports: tmp/sec-ops/"
Write-Host "Guide: docs/infra/sec-ops.md"
