"""Static checks on the rendered chart. They need the helm binary, not a cluster."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
CHART = REPO / "app" / "infra" / "helm" / "knowledge-platform"
DESKTOP = CHART / "values-desktop.yaml"

pytestmark = pytest.mark.skipif(shutil.which("helm") is None, reason="needs helm")


def render(*args: str) -> list[dict]:
    out = subprocess.run(
        ["helm", "template", "kp", str(CHART), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    ).stdout
    return [doc for doc in yaml.safe_load_all(out) if doc]


@pytest.fixture(scope="module", params=[(), ("-f", str(DESKTOP))], ids=["base", "desktop"])
def manifests(request) -> list[dict]:
    return render(*request.param)


def deployments(docs: list[dict]) -> list[dict]:
    return [d for d in docs if d["kind"] == "Deployment"]


def test_every_workload_is_covered(manifests):
    names = {d["metadata"]["name"] for d in deployments(manifests)}
    assert names == {"api", "frontend", "postgres", "neo4j", "qdrant", "redis", "minio"}


def test_pods_meet_the_restricted_standard(manifests):
    for deployment in deployments(manifests):
        name = deployment["metadata"]["name"]
        spec = deployment["spec"]["template"]["spec"]
        pod = spec["securityContext"]
        assert pod["runAsNonRoot"] is True, name
        assert pod["runAsUser"] > 0, name
        assert pod["seccompProfile"]["type"] == "RuntimeDefault", name
        assert spec["automountServiceAccountToken"] is False, name
        for container in spec["containers"]:
            security = container["securityContext"]
            assert security["allowPrivilegeEscalation"] is False, name
            assert security["capabilities"]["drop"] == ["ALL"], name


def test_writable_rootfs_is_only_allowed_with_a_stated_reason(manifests):
    for deployment in deployments(manifests):
        template = deployment["spec"]["template"]
        exception = template["metadata"]["labels"].get("kp.retailpartnerx.io/writable-rootfs")
        read_only = template["spec"]["containers"][0]["securityContext"]["readOnlyRootFilesystem"]
        assert read_only is (exception is None), deployment["metadata"]["name"]


def test_application_pods_have_read_only_rootfs(manifests):
    for deployment in deployments(manifests):
        if deployment["metadata"]["name"] in {"api", "frontend", "postgres", "redis"}:
            security = deployment["spec"]["template"]["spec"]["containers"][0]["securityContext"]
            assert security["readOnlyRootFilesystem"] is True


def test_namespace_enforces_restricted(manifests):
    namespace = next(d for d in manifests if d["kind"] == "Namespace")
    assert namespace["metadata"]["labels"]["pod-security.kubernetes.io/enforce"] == "restricted"


def test_network_is_default_deny_with_no_open_rules(manifests):
    policies = [d for d in manifests if d["kind"] == "NetworkPolicy"]
    deny = next(p for p in policies if p["metadata"]["name"] == "kp-default-deny")
    assert deny["spec"]["podSelector"] == {}
    assert sorted(deny["spec"]["policyTypes"]) == ["Egress", "Ingress"]
    assert "ingress" not in deny["spec"]
    assert "egress" not in deny["spec"]
    for policy in policies:
        for rule in policy["spec"].get("ingress", []) + policy["spec"].get("egress", []):
            assert rule.get("from") or rule.get("to"), f"{policy['metadata']['name']} has a rule with no peer"
            assert rule.get("ports"), f"{policy['metadata']['name']} has a rule with no port limit"


def test_only_the_api_can_reach_each_store(manifests):
    policies = {d["metadata"]["name"]: d for d in manifests if d["kind"] == "NetworkPolicy"}
    for store in ("postgres", "neo4j", "qdrant", "redis", "minio"):
        first_rule = policies[f"kp-{store}"]["spec"]["ingress"][0]
        assert first_rule["from"] == [{"podSelector": {"matchLabels": {"app": "api"}}}]


def test_no_plaintext_password_in_pod_env(manifests):
    for deployment in deployments(manifests):
        for container in deployment["spec"]["template"]["spec"]["containers"]:
            for env in container.get("env", []):
                if env["name"] in {"POSTGRES_DSN", "POSTGRES_PASSWORD", "NEO4J_AUTH", "NEO4J_PASSWORD"}:
                    assert "valueFrom" in env, f"{deployment['metadata']['name']}: {env['name']}"


def test_kyverno_policies_are_optional_and_enforcing():
    assert not [d for d in render() if d["kind"] == "ClusterPolicy"]
    policies = [d for d in render("--set", "kyverno.enabled=true") if d["kind"] == "ClusterPolicy"]
    assert {p["metadata"]["name"] for p in policies} == {
        "kp-pod-security-restricted",
        "kp-read-only-rootfs",
        "kp-disallow-mutable-images",
    }
    for policy in policies:
        for rule in policy["spec"]["rules"]:
            assert rule["validate"]["failureAction"] == "Enforce"
