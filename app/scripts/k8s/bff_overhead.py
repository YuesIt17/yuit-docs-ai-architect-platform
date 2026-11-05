"""Measure what the BFF adds, from a pod inside the cluster, so neither the ingress nor the host's network is included.

Each round calls the API directly with the bearer token and through the BFF with the session cookie, on the same
endpoint and in alternating blocks, so drift affects both sides equally. Both sides include the API's JWT validation.

It decrypts the session from Redis to get the token for the direct calls, which needs the session key. It is a
measurement tool for the demo values only. See architecture/adr/ADR-010-bff-auth.md for how to run it.

    python bff_overhead.py --cookie <session id> --key <base64 session key>
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import statistics
import time
from concurrent.futures import ThreadPoolExecutor

import httpx
import redis
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

API = "http://api:8080"
BFF = "http://bff:8080"
SESSION_COOKIE = "__Host-kp_session"
NONCE_BYTES = 12


def load_session(cookie: str, key_b64: str) -> dict:
    key = f"bff:session:{hashlib.sha256(cookie.encode()).hexdigest()}"
    sealed = redis.Redis(host="redis", port=6379, db=1).get(key)
    if sealed is None:
        raise SystemExit("session not found: log in again")
    plain = AESGCM(base64.b64decode(key_b64)).decrypt(sealed[:NONCE_BYTES], sealed[NONCE_BYTES:], key.encode())
    return json.loads(plain)


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(len(ordered) * fraction))]


def row(name: str, direct: list[float], bff: list[float]) -> None:
    print(f"\n{name}  (n={len(direct)} per side, ms)")
    print(f"{'':10}{'direct':>10}{'via BFF':>10}{'added':>10}")
    for label, fraction in (("p50", 0.5), ("p95", 0.95), ("p99", 0.99)):
        d, b = percentile(direct, fraction) * 1000, percentile(bff, fraction) * 1000
        print(f"{label:10}{d:10.2f}{b:10.2f}{b - d:10.2f}")
    print(f"{'mean':10}{statistics.mean(direct) * 1000:10.2f}{statistics.mean(bff) * 1000:10.2f}"
          f"{(statistics.mean(bff) - statistics.mean(direct)) * 1000:10.2f}")


def timed_get(client: httpx.Client, url: str, headers: dict[str, str]) -> float:
    started = time.perf_counter()
    res = client.get(url, headers=headers)
    elapsed = time.perf_counter() - started
    if res.status_code != 200:
        raise SystemExit(f"{url} answered {res.status_code}")
    return elapsed


def sequential(direct_h: dict, bff_h: dict, rounds: int, block: int) -> tuple[list[float], list[float]]:
    direct: list[float] = []
    bff: list[float] = []
    with httpx.Client(timeout=30, trust_env=False) as client:
        timed_get(client, f"{API}/v1/me", direct_h)
        timed_get(client, f"{BFF}/api/v1/me", bff_h)
        for _ in range(rounds):
            direct += [timed_get(client, f"{API}/v1/me", direct_h) for _ in range(block)]
            bff += [timed_get(client, f"{BFF}/api/v1/me", bff_h) for _ in range(block)]
    return direct, bff


def concurrent(url: str, headers: dict, workers: int, per_worker: int) -> tuple[list[float], float]:
    def work(_: int) -> list[float]:
        with httpx.Client(timeout=60, trust_env=False) as client:
            return [timed_get(client, url, headers) for _ in range(per_worker)]

    started = time.perf_counter()
    with ThreadPoolExecutor(workers) as pool:
        batches = list(pool.map(work, range(workers)))
    return [t for batch in batches for t in batch], time.perf_counter() - started


def stream_first_event(client: httpx.Client, url: str, headers: dict, session_id: str) -> tuple[float, float]:
    body = {"message": "What allergens are in FreshFarm oats?", "session_id": session_id, "stream": True}
    started = time.perf_counter()
    first = None
    with client.stream("POST", url, headers=headers, json=body) as res:
        if res.status_code != 200:
            raise SystemExit(f"{url} answered {res.status_code}")
        for chunk in res.iter_bytes():
            if chunk and first is None:
                first = time.perf_counter() - started
    return first or 0.0, time.perf_counter() - started


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cookie", required=True)
    parser.add_argument("--key", required=True)
    parser.add_argument("--rounds", type=int, default=15)
    parser.add_argument("--block", type=int, default=100)
    parser.add_argument("--streams", type=int, default=60)
    args = parser.parse_args()

    session = load_session(args.cookie, args.key)
    direct_h = {"Authorization": f"Bearer {session['access_token']}"}
    bff_h = {"Cookie": f"{SESSION_COOKIE}={args.cookie}"}
    write_h = {**bff_h, "X-CSRF-Token": session["csrf_token"], "Sec-Fetch-Site": "same-origin"}

    row("GET /v1/me, sequential", *sequential(direct_h, bff_h, args.rounds, args.block))

    for workers in (8, 16):
        direct, direct_s = concurrent(f"{API}/v1/me", direct_h, workers, 100)
        bff, bff_s = concurrent(f"{BFF}/api/v1/me", bff_h, workers, 100)
        row(f"GET /v1/me, {workers} clients", direct, bff)
        print(f"throughput  direct {len(direct) / direct_s:.0f} req/s, via BFF {len(bff) / bff_s:.0f} req/s")

    first_d, first_b, total_d, total_b = [], [], [], []
    with httpx.Client(timeout=60, trust_env=False) as client:
        for i in range(args.streams):
            f, t = stream_first_event(client, f"{API}/v1/chat", direct_h, f"bench-d-{i}")
            first_d.append(f)
            total_d.append(t)
            f, t = stream_first_event(client, f"{BFF}/api/v1/chat", write_h, f"bench-b-{i}")
            first_b.append(f)
            total_b.append(t)
    row("POST /v1/chat stream, time to first bytes", first_d, first_b)
    row("POST /v1/chat stream, total", total_d, total_b)


if __name__ == "__main__":
    main()
