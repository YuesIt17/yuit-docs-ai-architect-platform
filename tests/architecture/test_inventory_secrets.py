"""Inventory sanitization and consistency smoke tests."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
TOOLS = REPO / "tools" / "diagrams"
sys.path.insert(0, str(TOOLS))

from extract_inventory import (  # noqa: E402
    parse_k8s_resources,
    sanitize_manifest_yaml,
)
from check_consistency import check_source_map, check_secrets_in_outputs  # noqa: E402


FIXTURE = """
apiVersion: v1
kind: Secret
metadata:
  name: kp-secrets
stringData:
  jwt-secret: super-real-password-do-not-leak
  postgres-password: RealPassw0rd!
---
apiVersion: v1
kind: Service
metadata:
  name: api
spec:
  ports:
    - port: 8080
      targetPort: 8080
  selector:
    app: api
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: kp-demo-pvc
spec:
  resources:
    requests:
      storage: 1Gi
"""


def test_secret_sanitized_not_in_output():
    sanitized = sanitize_manifest_yaml(FIXTURE)
    assert "super-real-password-do-not-leak" not in sanitized
    assert "RealPassw0rd" not in sanitized
    assert "fixture-value" in sanitized
    docs = list(yaml.safe_load_all(sanitized))
    secret = next(d for d in docs if d and d.get("kind") == "Secret")
    assert secret["stringData"]["jwt-secret"] == "fixture-value"


def test_service_port_and_pvc_in_inventory():
    resources = parse_k8s_resources(sanitize_manifest_yaml(FIXTURE))
    svc = next(r for r in resources if r["kind"] == "Service" and r["name"] == "api")
    assert svc["ports"][0]["port"] == 8080
    pvc = next(r for r in resources if r["kind"] == "PersistentVolumeClaim")
    assert pvc["name"] == "kp-demo-pvc"
    assert pvc["storage"] == "1Gi"


def test_port_change_detected():
    altered = FIXTURE.replace("port: 8080", "port: 9090", 1)
    resources = parse_k8s_resources(sanitize_manifest_yaml(altered))
    svc = next(r for r in resources if r["kind"] == "Service")
    assert svc["ports"][0]["port"] == 9090


def test_source_map_symbols_exist():
    errors = check_source_map()
    assert errors == [], errors


def test_no_secrets_in_generated_if_present():
    gen = REPO / "architecture" / "diagrams"
    if not gen.exists():
        return
    errors = check_secrets_in_outputs(gen)
    assert errors == [], errors
