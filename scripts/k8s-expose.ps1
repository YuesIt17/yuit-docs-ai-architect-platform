<#
.SYNOPSIS
  Stable local access to kind ingress on Docker Desktop (Windows/macOS).

  kind extraPortMappings (host:8088 -> node:80) often reset under Docker load.
  This script keeps a kubectl port-forward to ingress-nginx on 127.0.0.1:8088.

.USAGE
  .\scripts\k8s-expose.ps1
  .\scripts\k8s-expose.ps1 -Port 8088
#>
param(
  [int]$Port = 8088,
  [string]$Namespace = "ingress-nginx",
  [string]$Service = "ingress-nginx-controller"
)

$ErrorActionPreference = "Stop"

function Test-Ingress([int]$p) {
  try {
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:$p/api/health" -Headers @{ Host = "kp.local" } -UseBasicParsing -TimeoutSec 3
    return $r.StatusCode -eq 200
  } catch {
    return $false
  }
}

Write-Host "==> Exposing ingress via kubectl port-forward on 127.0.0.1:$Port"
Write-Host "    UI:  http://kp.local:$Port  (or Host: kp.local)"
Write-Host "    API: http://127.0.0.1:$Port/api/health"
Write-Host "    Ctrl+C to stop"
Write-Host ""

# Fail fast if cluster is down (Docker Desktop often flaps).
$nodes = kubectl get nodes --request-timeout=5s 2>&1
if ($LASTEXITCODE -ne 0) {
  Write-Host "ERROR: kubectl cannot reach the cluster."
  Write-Host $nodes
  Write-Host "Start Docker Desktop + kind nodes, then re-run .\scripts\k8s-expose.ps1"
  exit 1
}

# Free stale listeners on the port (previous port-forwards).
Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue |
  ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }

$backoff = 2
while ($true) {
  if (Test-Ingress $Port) {
    Start-Sleep 5
    continue
  }

  Write-Host "$(Get-Date -Format HH:mm:ss) port-forward restart (ingress not healthy on :$Port)"
  Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue |
    ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }

  $proc = Start-Process -FilePath "kubectl" -ArgumentList @(
    "-n", $Namespace, "port-forward", "svc/$Service", "${Port}:80", "--address=127.0.0.1"
  ) -PassThru -WindowStyle Hidden

  Start-Sleep $backoff
  if ($backoff -lt 30) { $backoff = [Math]::Min(30, $backoff * 2) }

  # If kubectl exited immediately, wait before retry.
  if ($proc.HasExited) {
    Write-Host "kubectl exited with code $($proc.ExitCode); retrying..."
    Start-Sleep 3
  }
}
