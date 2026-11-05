"""End-to-end check of real login on a running cluster, with the demo users from values-desktop-oidc.yaml.

It drives the browser's side of the flow over HTTP: the Keycloak login form, the session cookie, the stream and logout.

    python app/scripts/k8s/oidc_e2e.py --base-url http://kp.localhost:8088
"""

from __future__ import annotations

import argparse
import json
import re
import socket
import sys
import time
from dataclasses import dataclass, field
from html import unescape
from urllib.parse import urljoin, urlparse

import httpx

_system_getaddrinfo = socket.getaddrinfo


def _resolve_localhost_names(host, *args, **kwargs):
    """Browsers resolve *.localhost to loopback themselves, but the Windows resolver does not."""
    if isinstance(host, str) and host.endswith(".localhost"):
        host = "127.0.0.1"
    return _system_getaddrinfo(host, *args, **kwargs)


socket.getaddrinfo = _resolve_localhost_names

SESSION_COOKIE = "__Host-kp_session"
SECRET_QUESTION = "Tell me about the Q4 Closed Promo Margin Playbook and the 42% margin"
INTERNAL_QUESTION = "What does the Allergen Shelf Labeling Policy say?"
TOKEN_PATTERN = re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.")
# Keycloak's own login cookies, scoped to its path. KEYCLOAK_IDENTITY is a signed JWT the API cannot accept.
IDP_COOKIE_PREFIXES = ("KEYCLOAK_", "AUTH_SESSION", "KC_")

# username, password, expected role, classifications the role may see.
USERS = [
    ("guest", "kp-demo-guest", "guest", {"public"}),
    ("associate", "kp-demo-associate", "store_associate", {"public", "internal"}),
    ("manager", "kp-demo-manager", "category_manager", {"public", "internal"}),
    ("compliance", "kp-demo-compliance", "compliance_officer", {"public", "internal", "secret"}),
]


@dataclass
class Browser:
    """Keeps cookies by hand: http.cookiejar withholds Secure cookies over HTTP, which browsers allow on *.localhost."""

    base: str
    client: httpx.Client = field(default_factory=lambda: httpx.Client(timeout=60.0, trust_env=False))
    cookies: dict[str, str] = field(default_factory=dict)
    set_cookie_headers: list[str] = field(default_factory=list)
    seen_bodies: list[str] = field(default_factory=list)

    def _absorb(self, res: httpx.Response) -> None:
        for raw in res.headers.get_list("set-cookie"):
            self.set_cookie_headers.append(raw)
            name, _, rest = raw.partition("=")
            value = rest.split(";", 1)[0]
            if "max-age=0" in raw.lower() or not value:
                self.cookies.pop(name, None)
            else:
                self.cookies[name] = value

    def request(self, method: str, url: str, **kwargs) -> httpx.Response:
        url = urljoin(self.base + "/", url)
        headers = dict(kwargs.pop("headers", {}))
        if self.cookies:
            headers["Cookie"] = "; ".join(f"{k}={v}" for k, v in self.cookies.items())
        res = self.client.request(method, url, headers=headers, **kwargs)
        self._absorb(res)
        self.seen_bodies.append(res.text)
        return res

    def follow(self, res: httpx.Response) -> httpx.Response:
        while res.is_redirect:
            res = self.request("GET", urljoin(str(res.url), res.headers["location"]))
        return res


def login(browser: Browser, username: str, password: str) -> httpx.Response:
    page = browser.follow(browser.request("GET", "/auth/login"))
    match = re.search(r'action="([^"]+)"', page.text)
    if not match:
        raise AssertionError(f"no login form at {page.url}: {page.status_code}")
    form_url = urljoin(str(page.url), unescape(match.group(1)))
    assert urlparse(form_url).path.startswith("/idp/realms/"), form_url
    posted = browser.request("POST", form_url, data={"username": username, "password": password})
    return browser.follow(posted)


def stream_chat(browser: Browser, csrf: str, message: str, session_id: str) -> tuple[dict, float, float, list[str]]:
    """Returns the final event, time to the first event, total time, and the event names in order."""
    url = urljoin(browser.base + "/", "/api/v1/chat")
    headers = {
        "Cookie": f"{SESSION_COOKIE}={browser.cookies[SESSION_COOKIE]}",
        "X-CSRF-Token": csrf,
        "Sec-Fetch-Site": "same-origin",
        "Content-Type": "application/json",
    }
    body = {"message": message, "session_id": session_id, "stream": True}
    started = time.perf_counter()
    first = None
    events: list[str] = []
    final: dict = {}
    event = ""
    with browser.client.stream("POST", url, headers=headers, json=body) as res:
        assert res.status_code == 200, res.status_code
        assert res.headers["content-type"].startswith("text/event-stream"), res.headers["content-type"]
        for line in res.iter_lines():
            if line.startswith("event:"):
                event = line[6:].strip()
                events.append(event)
                first = first or time.perf_counter() - started
            elif line.startswith("data:") and event == "final":
                final = json.loads(line[5:].strip())
    return final, first or 0.0, time.perf_counter() - started, events


def check(results: list[str], name: str, ok: bool, detail: str = "") -> None:
    results.append(f"{'PASS' if ok else 'FAIL'}  {name}{'  ' + detail if detail else ''}")


def check_user(base: str, username: str, password: str, role: str, allowed: set[str], results: list[str]) -> str:
    browser = Browser(base)
    prefix = f"[{username}]"

    denied = browser.request("GET", "/api/v1/graph/stats")
    check(results, f"{prefix} API needs a session", denied.status_code == 401, str(denied.status_code))

    bad = Browser(base)
    page = login(bad, username, "wrong-password")
    check(results, f"{prefix} wrong password gets no session", SESSION_COOKIE not in bad.cookies, str(page.status_code))

    login(browser, username, password)
    check(results, f"{prefix} login sets the session cookie", SESSION_COOKIE in browser.cookies)
    raw = next((c for c in browser.set_cookie_headers if c.startswith(SESSION_COOKIE)), "").lower()
    strict = all(attr in raw for attr in ("httponly", "secure", "samesite=lax", "path=/")) and "domain=" not in raw
    check(results, f"{prefix} cookie is strict", strict)

    me = browser.request("GET", "/auth/me")
    body = me.json()
    check(results, f"{prefix} /auth/me role", body.get("role") == role, str(body.get("role")))
    sub = body.get("user_id", "")
    check(results, f"{prefix} user_id is the token sub", bool(re.fullmatch(r"[0-9a-f-]{36}", sub)), sub)
    check(results, f"{prefix} /auth/me clearance", set(body.get("allowed_classifications", [])) == allowed)
    csrf = body["csrf_token"]

    for internal_path in ("/api/metrics", "/api/docs", "/api/openapi.json"):
        res = browser.request("GET", internal_path)
        check(results, f"{prefix} {internal_path} stays internal", res.status_code == 404, str(res.status_code))

    no_csrf = browser.request("POST", "/api/v1/chat", json={"message": "hi", "stream": False})
    check(results, f"{prefix} POST without CSRF token is refused", no_csrf.status_code == 403, str(no_csrf.status_code))

    forged = browser.request(
        "POST",
        "/api/v1/chat",
        json={"message": "hi", "stream": False},
        headers={"X-CSRF-Token": csrf, "Origin": "https://evil.example"},
    )
    check(results, f"{prefix} foreign origin is refused", forged.status_code == 403, str(forged.status_code))

    final, first, total, events = stream_chat(browser, csrf, SECRET_QUESTION, f"e2e-{username}")
    classes = sorted({c["classification"] for c in final.get("citations", [])})
    check(results, f"{prefix} chat streams", events[:1] == ["meta"] and events[-1:] == ["final"], str(events))
    results.append(f"INFO  {prefix} first event {first * 1000:.0f} ms, total {total * 1000:.0f} ms, classes {classes}")
    if "secret" in allowed:
        check(results, f"{prefix} sees the secret document", "secret" in classes, final.get("acl_decision", ""))
    else:
        leaked = "secret" in classes or "42%" in final.get("answer", "")
        check(results, f"{prefix} does not see the secret document", not leaked, final.get("acl_decision", ""))

    final, _, _, _ = stream_chat(browser, csrf, INTERNAL_QUESTION, f"e2e-internal-{username}")
    classes = sorted({c["classification"] for c in final.get("citations", [])})
    check(results, f"{prefix} citations stay within clearance", set(classes) <= allowed, str(classes))
    if "internal" in allowed:
        check(results, f"{prefix} sees the internal document", "internal" in classes, str(classes))
    else:
        check(results, f"{prefix} does not see the internal document", "internal" not in classes, str(classes))

    leaks = [b for b in browser.seen_bodies if TOKEN_PATTERN.search(b)]
    check(results, f"{prefix} no JWT reached the browser", not leaks)
    ours = "".join(v for k, v in browser.cookies.items() if not k.startswith(IDP_COOKIE_PREFIXES))
    check(results, f"{prefix} no JWT in the BFF's cookies", not TOKEN_PATTERN.search(ours))
    idp = next((c for c in browser.set_cookie_headers if c.startswith("KEYCLOAK_IDENTITY=")), "").lower()
    scoped = "httponly" in idp and "/idp/realms/" in idp
    check(results, f"{prefix} the IdP's cookie is HttpOnly and path-scoped", scoped)

    out = browser.request("POST", "/auth/logout", headers={"X-CSRF-Token": csrf, "Sec-Fetch-Site": "same-origin"})
    ended = out.status_code == 200 and out.json().get("idp_session_ended") is True
    check(results, f"{prefix} logout ends the Keycloak session", ended, out.text)
    check(results, f"{prefix} cookie cleared", SESSION_COOKIE not in browser.cookies)

    # Keycloak's own cookies are kept here. A live IdP session would log straight in without showing a form.
    page = browser.follow(browser.request("GET", "/auth/login"))
    prompted = 'name="password"' in page.text
    check(results, f"{prefix} next login needs the password again", prompted, str(page.status_code))
    return sub


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://kp.localhost:8088")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")
    results: list[str] = []

    with httpx.Client(timeout=10.0, trust_env=False) as anonymous:
        mode = anonymous.get(f"{base}/api/v1/auth/mode")
        check(results, "auth mode is oidc", mode.json() == {"mode": "oidc"}, mode.text)
        for path, statuses in {
            "/api/metrics": {401},
            "/api/docs": {401},
            "/idp/admin/": {200, 404},
            "/api/v1/me": {401},
        }.items():
            res = anonymous.get(f"{base}{path}")
            ok = res.status_code in statuses and (path != "/idp/admin/" or "Keycloak Administration" not in res.text)
            check(results, f"anonymous {path}", ok, str(res.status_code))
        demo = anonymous.get(f"{base}/api/v1/me", headers={"Authorization": "Bearer compliance"})
        check(results, "demo token is refused", demo.status_code == 401, str(demo.status_code))

    subjects = [check_user(base, *user, results) for user in USERS]
    check(results, "each user has their own sub", len(set(subjects)) == len(USERS))

    print("\n".join(results))
    failures = [r for r in results if r.startswith("FAIL")]
    print(f"\n{len(results) - len(failures)} passed or informational, {len(failures)} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
