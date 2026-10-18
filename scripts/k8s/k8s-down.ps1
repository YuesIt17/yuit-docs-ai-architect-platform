$ErrorActionPreference = "Stop"

Write-Host "==> helm uninstall kp"
helm uninstall kp -n kp 2>$null

if ($env:KP_K8S -eq "kind") {
  $cluster = "retailpartnerx-kp"
  Write-Host "==> kind delete cluster $cluster"
  kind delete cluster --name $cluster 2>$null
} else {
  Write-Host "==> Leaving docker-desktop cluster; uninstall ingress-nginx? skip (shared)"
  Write-Host "    To reset K8s entirely: Docker Desktop -> Settings -> Kubernetes -> Reset"
}

Write-Host "Done."
