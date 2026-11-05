"""Static checks on the rendered chart. They need the helm binary, not a cluster."""

from __future__ import annotations

import json
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


def test_minio_runtime_paths_are_writable_without_group_root(manifests):
    minio = next(d for d in deployments(manifests) if d["metadata"]["name"] == "minio")
    assert minio["spec"]["template"]["spec"]["securityContext"]["runAsGroup"] != 0
    mounts = {m["mountPath"] for m in minio["spec"]["template"]["spec"]["containers"][0]["volumeMounts"]}
    assert {"/opt/bitnami/minio/tmp", "/opt/bitnami/minio/secrets", "/.mc"} <= mounts


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


def test_external_secrets_replaces_the_helm_secret_and_mounts_the_dsn():
    docs = render("--set", "secrets.provider=external-secrets")
    assert not [d for d in docs if d["kind"] == "Secret"]
    assert {d["metadata"]["name"] for d in docs if d["kind"] == "ExternalSecret"} == {"kp-secrets", "kp-postgres-dsn"}
    api = next(d for d in deployments(docs) if d["metadata"]["name"] == "api")
    env = {e["name"] for e in api["spec"]["template"]["spec"]["containers"][0]["env"]}
    assert "POSTGRES_DSN_FILE" in env
    assert "POSTGRES_DSN" not in env


def test_dsn_refresh_is_shorter_than_the_vault_lease():
    docs = render("--set", "secrets.provider=external-secrets")
    dynamic = next(d for d in docs if d["kind"] == "ExternalSecret" and d["metadata"]["name"] == "kp-postgres-dsn")
    assert dynamic["spec"]["refreshInterval"] == "30m"


def test_api_gets_store_credentials_from_the_secret(manifests):
    api = next(d for d in deployments(manifests) if d["metadata"]["name"] == "api")
    env = {e["name"]: e for e in api["spec"]["template"]["spec"]["containers"][0]["env"]}
    for name in ("NEO4J_PASSWORD", "MINIO_ACCESS_KEY", "MINIO_SECRET_KEY", "JWT_SECRET"):
        assert "secretKeyRef" in env[name]["valueFrom"]


def test_worker_is_hardened_and_can_reach_stores_when_enabled():
    docs = render("--set", "worker.enabled=true")
    worker = next(d for d in deployments(docs) if d["metadata"]["name"] == "worker")
    spec = worker["spec"]["template"]["spec"]
    assert spec["securityContext"]["runAsNonRoot"] is True
    assert spec["containers"][0]["securityContext"]["readOnlyRootFilesystem"] is True
    postgres = next(d for d in docs if d["kind"] == "NetworkPolicy" and d["metadata"]["name"] == "kp-postgres")
    assert {"podSelector": {"matchLabels": {"app": "worker"}}} in postgres["spec"]["ingress"][0]["from"]


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


# --- Real login: Keycloak and the BFF ---

OIDC_DESKTOP = CHART / "values-desktop-oidc.yaml"
OIDC_FLAGS = (
    "--set", "bff.enabled=true",
    "--set", "keycloak.enabled=true",
    "--set", "bff.publicUrl=https://kp.example",
    "--set", "bff.sessionEncryptionKey=a2V5",
    "--set", "bff.oidc.clientSecret=secret",
    "--set", "keycloak.adminPassword=admin",
)  # fmt: skip


@pytest.fixture(
    scope="module",
    params=[OIDC_FLAGS, ("-f", str(DESKTOP), "-f", str(OIDC_DESKTOP))],
    ids=["base-oidc", "desktop-oidc"],
)
def oidc(request) -> list[dict]:
    return render(*request.param)


def by_name(docs: list[dict], kind: str, name: str) -> dict:
    return next(d for d in docs if d["kind"] == kind and d["metadata"]["name"] == name)


def env_of(docs: list[dict], deployment: str) -> dict[str, dict]:
    spec = by_name(docs, "Deployment", deployment)["spec"]["template"]["spec"]
    return {e["name"]: e for e in spec["containers"][0]["env"]}


def test_login_stack_is_off_by_default(manifests):
    names = {d["metadata"]["name"] for d in deployments(manifests)}
    assert not names & {"bff", "keycloak"}
    env = env_of(manifests, "api")
    assert env["DEMO_AUTH_ENABLED"]["value"] == "true"
    assert not {"OIDC_ISSUER", "OIDC_JWKS_URL"} & set(env)
    assert not [d for d in manifests if d["kind"] == "Ingress" and d["metadata"]["name"] in {"kp-bff", "kp-idp"}]


def test_login_stack_workloads_meet_restricted_with_read_only_rootfs(oidc):
    for name in ("bff", "keycloak"):
        template = by_name(oidc, "Deployment", name)["spec"]["template"]
        spec = template["spec"]
        assert spec["securityContext"]["runAsNonRoot"] is True, name
        assert spec["securityContext"]["runAsUser"] > 0, name
        assert spec["securityContext"]["seccompProfile"]["type"] == "RuntimeDefault", name
        assert spec["automountServiceAccountToken"] is False, name
        security = spec["containers"][0]["securityContext"]
        assert security["readOnlyRootFilesystem"] is True, name
        assert security["allowPrivilegeEscalation"] is False, name
        assert security["capabilities"]["drop"] == ["ALL"], name
        assert "kp.retailpartnerx.io/writable-rootfs" not in template["metadata"]["labels"], name


def test_bff_image_is_distroless_and_non_root():
    dockerfile = (REPO / "app" / "bff" / "Dockerfile").read_text(encoding="utf-8")
    final_stage = dockerfile[dockerfile.rindex("FROM ") :]
    assert final_stage.startswith("FROM gcr.io/distroless/static-")
    assert ":nonroot" in final_stage.splitlines()[0]
    assert "USER 65532" in final_stage


def test_api_is_in_oidc_mode_and_the_modes_cannot_mix(oidc):
    env = env_of(oidc, "api")
    assert env["DEMO_AUTH_ENABLED"]["value"] == "false"
    assert env["OIDC_ISSUER"]["value"].endswith("/idp/realms/kp")
    assert env["OIDC_AUDIENCE"]["value"] == "kp-api"
    assert env["OIDC_JWKS_URL"]["value"] == "http://keycloak:8080/idp/realms/kp/protocol/openid-connect/certs"


def test_values_cannot_turn_demo_auth_back_on_with_the_bff():
    docs = render(*OIDC_FLAGS, "--set", "api.env.DEMO_AUTH_ENABLED=true")
    assert env_of(docs, "api")["DEMO_AUTH_ENABLED"]["value"] == "false"


def test_bff_and_api_agree_on_the_issuer(oidc):
    assert env_of(oidc, "bff")["OIDC_ISSUER_URL"]["value"] == env_of(oidc, "api")["OIDC_ISSUER"]["value"]


def test_only_the_bff_reaches_the_api(oidc):
    api = by_name(oidc, "NetworkPolicy", "kp-api")
    assert len(api["spec"]["ingress"]) == 1
    assert api["spec"]["ingress"][0]["from"] == [{"podSelector": {"matchLabels": {"app": "bff"}}}]
    assert by_name(oidc, "Service", "api")["spec"]["type"] == "ClusterIP"
    assert "egress" not in by_name(oidc, "NetworkPolicy", "kp-frontend")["spec"]


def test_ingress_never_routes_to_the_api_or_the_keycloak_admin(oidc):
    backends = {}
    for ingress in (d for d in oidc if d["kind"] == "Ingress"):
        for rule in ingress["spec"]["rules"]:
            for route in rule["http"]["paths"]:
                backends[route["path"]] = route["backend"]["service"]["name"]
    assert backends == {
        "/api": "bff",
        "/auth": "bff",
        "/idp/realms": "keycloak",
        "/idp/resources": "keycloak",
        "/": "frontend",
    }


def test_streaming_is_not_buffered_or_cut_by_the_ingress(oidc):
    annotations = by_name(oidc, "Ingress", "kp-bff")["metadata"]["annotations"]
    assert annotations["nginx.ingress.kubernetes.io/proxy-buffering"] == "off"
    assert int(annotations["nginx.ingress.kubernetes.io/proxy-read-timeout"]) >= 300


def test_frontend_nginx_no_longer_proxies_to_the_api(oidc):
    conf = by_name(oidc, "ConfigMap", "kp-frontend-nginx")["data"]["default.conf"]
    assert "proxy_pass" not in conf
    spec = by_name(oidc, "Deployment", "frontend")["spec"]["template"]["spec"]
    assert any(m["mountPath"] == "/etc/nginx/conf.d/default.conf" for m in spec["containers"][0]["volumeMounts"])


def test_bff_network_access_is_limited(oidc):
    policy = by_name(oidc, "NetworkPolicy", "kp-bff")["spec"]
    first = policy["ingress"][0]
    assert first["from"] == [{"namespaceSelector": {"matchLabels": {"kubernetes.io/metadata.name": "ingress-nginx"}}}]
    assert first["ports"] == [{"protocol": "TCP", "port": 8080}]
    for extra in policy["ingress"][1:]:
        assert extra["ports"] == [{"protocol": "TCP", "port": 9090}], "only the admin port may be open to the host"
    pods = {
        peer["podSelector"]["matchLabels"]["app"]
        for rule in policy["egress"]
        for peer in rule["to"]
        if "podSelector" in peer
    }
    assert pods == {"api", "redis", "keycloak"}


def test_of_the_stores_the_bff_reaches_only_redis(oidc):
    bff_peer = {"podSelector": {"matchLabels": {"app": "bff"}}}
    assert bff_peer in by_name(oidc, "NetworkPolicy", "kp-redis")["spec"]["ingress"][0]["from"]
    for store in ("postgres", "neo4j", "qdrant", "minio"):
        assert bff_peer not in by_name(oidc, "NetworkPolicy", f"kp-{store}")["spec"]["ingress"][0]["from"]


def test_keycloak_network_access_is_limited(oidc):
    policy = by_name(oidc, "NetworkPolicy", "kp-keycloak")["spec"]
    assert sorted(policy["policyTypes"]) == ["Egress", "Ingress"]
    assert "egress" not in policy
    assert policy["ingress"][0]["ports"] == [{"protocol": "TCP", "port": 8080}]
    peers = policy["ingress"][0]["from"]
    assert {"podSelector": {"matchLabels": {"app": "bff"}}} in peers
    assert {"podSelector": {"matchLabels": {"app": "api"}}} in peers
    assert len(peers) == 3


def test_login_secrets_never_appear_in_pod_env_or_a_configmap(oidc):
    bff = env_of(oidc, "bff")
    for name in ("OIDC_CLIENT_SECRET", "SESSION_ENCRYPTION_KEY"):
        assert "secretKeyRef" in bff[name]["valueFrom"]
    assert "secretKeyRef" in env_of(oidc, "keycloak")["KC_BOOTSTRAP_ADMIN_PASSWORD"]["valueFrom"]
    assert "realm.json" in by_name(oidc, "Secret", "kp-keycloak")["stringData"]
    for config_map in (d for d in oidc if d["kind"] == "ConfigMap"):
        assert "realm" not in str(config_map.get("data"))


def test_realm_has_one_demo_user_per_role_and_rotates_refresh_tokens():
    docs = render("-f", str(DESKTOP), "-f", str(OIDC_DESKTOP))
    realm = json.loads(by_name(docs, "Secret", "kp-keycloak")["stringData"]["realm.json"])
    assert {u["realmRoles"][0] for u in realm["users"]} == {
        "guest",
        "store_associate",
        "category_manager",
        "compliance_officer",
    }
    assert all(len(u["realmRoles"]) == 1 for u in realm["users"])
    assert {r["name"] for r in realm["roles"]["realm"]} == {u["realmRoles"][0] for u in realm["users"]}
    assert realm["revokeRefreshToken"] is True
    assert realm["refreshTokenMaxReuse"] == 0


def test_realm_client_is_confidential_with_pkce_and_exact_redirect():
    docs = render(*OIDC_FLAGS)
    realm = json.loads(by_name(docs, "Secret", "kp-keycloak")["stringData"]["realm.json"])
    client = realm["clients"][0]
    assert client["publicClient"] is False
    assert client["directAccessGrantsEnabled"] is False
    assert client["implicitFlowEnabled"] is False
    assert client["attributes"]["pkce.code.challenge.method"] == "S256"
    assert client["redirectUris"] == ["https://kp.example/auth/callback"]
    assert any(
        m["protocolMapper"] == "oidc-audience-mapper" and m["config"]["included.custom.audience"] == "kp-api"
        for m in client["protocolMappers"]
    )


@pytest.mark.parametrize(
    ("flags", "message"),
    [
        (("--set", "keycloak.enabled=true"), "needs bff.enabled"),
        (("--set", "bff.enabled=true"), "needs bff.publicUrl"),
        (("--set", "bff.enabled=true", "--set", "bff.publicUrl=https://kp.example"), "needs bff.oidc.issuerUrl"),
        ((*OIDC_FLAGS, "--set", "secrets.provider=external-secrets"), "needs secrets.provider=helm"),
    ],
)
def test_configurations_that_cannot_work_are_refused(flags, message):
    with pytest.raises(subprocess.CalledProcessError) as failure:
        render(*flags)
    assert message in failure.value.stderr


def test_bff_requires_its_own_secrets():
    flags = ("--set", "bff.enabled=true", "--set", "bff.publicUrl=https://kp.example",
             "--set", "bff.oidc.issuerUrl=https://idp.example/realms/kp")  # fmt: skip
    with pytest.raises(subprocess.CalledProcessError) as failure:
        render(*flags)
    assert "is required" in failure.value.stderr


def test_external_idp_with_vault_uses_an_external_secret():
    docs = render(
        "--set", "secrets.provider=external-secrets",
        "--set", "bff.enabled=true",
        "--set", "bff.publicUrl=https://kp.example",
        "--set", "bff.oidc.issuerUrl=https://idp.example/realms/kp",
    )  # fmt: skip
    assert by_name(docs, "ExternalSecret", "kp-bff-secrets")["spec"]["dataFrom"] == [{"extract": {"key": "kp/bff"}}]
    assert not [d for d in docs if d["kind"] == "Secret"]
    assert not [d for d in deployments(docs) if d["metadata"]["name"] == "keycloak"]
    env = env_of(docs, "api")
    assert env["OIDC_ISSUER"]["value"] == "https://idp.example/realms/kp"
