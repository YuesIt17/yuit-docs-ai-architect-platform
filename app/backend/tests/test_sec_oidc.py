"""OIDC mode: every token is validated by the API, and nothing falls back to guest."""

from __future__ import annotations

import base64
import json
import time

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from pydantic import ValidationError

from kp.api import deps as api_deps
from kp.application.chat import ChatService
from kp.config import Settings, get_settings
from kp.main import app
from kp.security.rbac import (
    AuthError,
    AuthUnavailableError,
    JwksCache,
    OidcVerifier,
    Principal,
    UnknownRoleError,
    resolve_principal,
)

ISSUER = "http://kp.localhost:8088/idp/realms/kp"
AUDIENCE = "kp-api"
KID = "test-key"


@pytest.fixture(scope="module")
def signing_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(scope="module")
def jwks(signing_key):
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(signing_key.public_key()))
    jwk.update(kid=KID, use="sig", alg="RS256")
    return {"keys": [jwk]}


def make_verifier(jwks_doc) -> OidcVerifier:
    return OidcVerifier(
        issuer=ISSUER,
        audience=AUDIENCE,
        algorithms=["RS256"],
        jwks=JwksCache("http://jwks.invalid", fetch=lambda _url: jwks_doc),
    )


@pytest.fixture()
def verifier(jwks):
    return make_verifier(jwks)


def claims(**overrides):
    now = int(time.time())
    base = {
        "iss": ISSUER,
        "aud": ["kp-api", "account"],
        "sub": "11111111-aaaa-bbbb-cccc-222222222222",
        "iat": now,
        "exp": now + 300,
        "preferred_username": "manager",
        "realm_access": {"roles": ["default-roles-kp", "offline_access", "category_manager"]},
    }
    base.update(overrides)
    return {k: v for k, v in base.items() if v is not None}


def sign(key, payload, *, kid=KID, algorithm="RS256"):
    return jwt.encode(payload, key, algorithm=algorithm, headers={"kid": kid})


def resolve(verifier, token):
    return resolve_principal(f"Bearer {token}", demo_auth_enabled=False, verifier=verifier)


def test_valid_token_maps_sub_and_realm_role(verifier, signing_key):
    principal = resolve(verifier, sign(signing_key, claims()))
    assert principal.user_id == "11111111-aaaa-bbbb-cccc-222222222222"
    assert principal.role == "category_manager"
    assert principal.name == "manager"


@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param({"exp": int(time.time()) - 3600}, id="expired"),
        pytest.param({"aud": "account"}, id="wrong-audience"),
        pytest.param({"iss": "http://evil.example/realms/kp"}, id="wrong-issuer"),
        pytest.param({"exp": None}, id="no-expiry"),
        pytest.param({"aud": None}, id="no-audience"),
        pytest.param({"sub": None}, id="no-subject"),
    ],
)
def test_bad_claims_are_rejected(verifier, signing_key, overrides):
    with pytest.raises(AuthError):
        resolve(verifier, sign(signing_key, claims(**overrides)))


@pytest.mark.parametrize(
    "roles",
    [
        pytest.param(["some_other_role"], id="unknown"),
        pytest.param([], id="empty"),
        pytest.param("category_manager", id="not-a-list"),
    ],
)
def test_token_without_platform_role_is_not_guest(verifier, signing_key, roles):
    with pytest.raises(UnknownRoleError):
        resolve(verifier, sign(signing_key, claims(realm_access={"roles": roles})))


def test_highest_clearance_role_wins_regardless_of_order(verifier, signing_key):
    token = sign(signing_key, claims(realm_access={"roles": ["guest", "compliance_officer", "store_associate"]}))
    assert resolve(verifier, token).role == "compliance_officer"


def test_token_from_another_key_is_rejected(verifier):
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    with pytest.raises(AuthError):
        resolve(verifier, sign(other, claims()))


def b64(data: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(data).encode()).rstrip(b"=").decode()


def test_alg_none_is_rejected(verifier):
    token = f"{b64({'alg': 'none', 'kid': KID})}.{b64(claims())}."
    with pytest.raises(AuthError):
        resolve(verifier, token)


def test_hmac_with_public_key_as_secret_is_rejected(verifier):
    token = sign("public-key-bytes-used-as-a-shared-secret-000000", claims(), algorithm="HS256")
    with pytest.raises(AuthError):
        resolve(verifier, token)


def test_garbage_and_demo_tokens_are_rejected_in_oidc_mode(verifier):
    for value in ("garbage", "manager", "compliance_officer"):
        with pytest.raises(AuthError):
            resolve(verifier, value)
    with pytest.raises(AuthError):
        resolve_principal(None, demo_auth_enabled=False, verifier=verifier)


def test_encryption_key_never_verifies_signatures(signing_key, jwks):
    enc = dict(jwks["keys"][0], use="enc")
    with pytest.raises(AuthError):
        resolve(make_verifier({"keys": [enc]}), sign(signing_key, claims()))


def test_unknown_kid_refresh_is_rate_limited(jwks):
    calls = []
    now = [1000.0]

    def fetch(_url):
        calls.append(1)
        return jwks

    cache = JwksCache("http://jwks.invalid", fetch=fetch, min_refresh_interval=30.0, clock=lambda: now[0])
    for _ in range(50):
        with pytest.raises(AuthError):
            cache.key_for("forged")
    assert len(calls) == 1
    now[0] += 31.0
    with pytest.raises(AuthError):
        cache.key_for("forged")
    assert len(calls) == 2


def test_rotated_key_is_picked_up(signing_key, jwks):
    old = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    old_jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(old.public_key()))
    old_jwk.update(kid="old-key", use="sig", alg="RS256")
    documents = [{"keys": [old_jwk]}, jwks]
    now = [1000.0]
    cache = JwksCache(
        "http://jwks.invalid",
        fetch=lambda _url: documents.pop(0),
        min_refresh_interval=30.0,
        clock=lambda: now[0],
    )
    with pytest.raises(AuthError):
        cache.key_for(KID)
    now[0] += 31.0
    assert cache.key_for(KID) is not None


def test_jwks_outage_is_unavailable_not_invalid():
    def fetch(_url):
        raise httpx.ConnectError("no route")

    cache = JwksCache("http://jwks.invalid", fetch=fetch)
    with pytest.raises(AuthUnavailableError):
        cache.key_for(KID)


def test_known_keys_survive_a_jwks_outage(jwks):
    responses = [jwks]
    now = [1000.0]

    def fetch(_url):
        if responses:
            return responses.pop()
        raise httpx.ConnectError("no route")

    cache = JwksCache("http://jwks.invalid", fetch=fetch, max_age=300.0, clock=lambda: now[0])
    assert cache.key_for(KID) is not None
    now[0] += 301.0
    assert cache.key_for(KID) is not None


def test_settings_refuse_to_mix_modes():
    with pytest.raises(ValidationError, match="cannot be mixed"):
        Settings(_env_file=None, demo_auth_enabled=True, oidc_issuer=ISSUER)
    assert Settings(_env_file=None, demo_auth_enabled=False, oidc_issuer=ISSUER).oidc_issuer == ISSUER


@pytest.mark.parametrize("algorithms", ["HS256", "none", "RS256,HS256", ""])
def test_settings_refuse_symmetric_or_empty_algorithms(algorithms):
    with pytest.raises(ValidationError, match="OIDC_ALGORITHMS"):
        Settings(_env_file=None, demo_auth_enabled=False, oidc_issuer=ISSUER, oidc_algorithms=algorithms)


def test_resolver_refuses_demo_flag_with_verifier(verifier):
    with pytest.raises(AuthError):
        resolve_principal("Bearer manager", demo_auth_enabled=True, verifier=verifier)


def test_threads_of_different_subjects_never_collide():
    first = Principal(user_id="sub-a", role="category_manager")
    second = Principal(user_id="sub-b", role="category_manager")
    assert ChatService.thread_id(first, "s1") != ChatService.thread_id(second, "s1")


@pytest.fixture()
def oidc_client(verifier, monkeypatch):
    settings = Settings(_env_file=None, demo_auth_enabled=False, oidc_issuer=ISSUER)
    api_deps.get_oidc_verifier.cache_clear()
    monkeypatch.setattr(api_deps, "get_settings", lambda: settings)
    monkeypatch.setattr(api_deps, "get_oidc_verifier", lambda: verifier)
    app.dependency_overrides[get_settings] = lambda: settings
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_http_valid_token_returns_me(oidc_client, signing_key):
    r = oidc_client.get("/v1/me", headers={"Authorization": f"Bearer {sign(signing_key, claims())}"})
    assert r.status_code == 200
    assert r.json() == {
        "user_id": "11111111-aaaa-bbbb-cccc-222222222222",
        "role": "category_manager",
        "name": "manager",
        "allowed_classifications": ["internal", "public"],
    }


@pytest.mark.parametrize(
    "path",
    ["/v1/me", "/v1/graph/stats", "/v1/graph/subgraph", "/v1/llm/config", "/v1/llm/health", "/v1/audit"],
)
def test_http_protected_routes_answer_401_without_a_token(oidc_client, path):
    r = oidc_client.get(path)
    assert r.status_code == 401
    assert r.headers["www-authenticate"] == "Bearer"


def test_http_chat_answers_401_for_demo_token(oidc_client):
    r = oidc_client.post("/v1/chat", json={"message": "hi"}, headers={"Authorization": "Bearer compliance"})
    assert r.status_code == 401


def test_http_expired_token_is_401_and_unknown_role_is_403(oidc_client, signing_key):
    expired = sign(signing_key, claims(exp=int(time.time()) - 3600))
    assert oidc_client.get("/v1/me", headers={"Authorization": f"Bearer {expired}"}).status_code == 401
    unknown = sign(signing_key, claims(realm_access={"roles": ["nope"]}))
    assert oidc_client.get("/v1/me", headers={"Authorization": f"Bearer {unknown}"}).status_code == 403


def test_http_mode_endpoint_is_public(oidc_client):
    r = oidc_client.get("/v1/auth/mode")
    assert r.status_code == 200
    assert r.json() == {"mode": "oidc"}


def test_http_acl_applies_to_a_jwt_principal(oidc_client, signing_key):
    """A manager's JWT must not retrieve the secret playbook; a compliance JWT may."""
    question = {"message": "Tell me about the Q4 Closed Promo Margin Playbook and the 42% margin", "stream": False}
    manager = sign(signing_key, claims())
    r = oidc_client.post("/v1/chat", json=question, headers={"Authorization": f"Bearer {manager}"})
    assert r.status_code == 200
    assert all(c["classification"] != "secret" for c in r.json()["citations"])

    officer = sign(signing_key, claims(sub="sub-comp", realm_access={"roles": ["compliance_officer"]}))
    r = oidc_client.post("/v1/chat", json=question, headers={"Authorization": f"Bearer {officer}"})
    assert r.status_code == 200
    assert any(c["classification"] == "secret" for c in r.json()["citations"])


def test_demo_mode_reports_demo():
    r = TestClient(app).get("/v1/auth/mode")
    assert r.status_code == 200
    assert r.json() == {"mode": "demo"}
