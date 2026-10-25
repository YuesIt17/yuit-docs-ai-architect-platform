#!/usr/bin/env python3
"""Readiness / effective providers / live fallback status for demo prep."""

from __future__ import annotations

import argparse
import json
import sys

import httpx


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--base-url", default="http://127.0.0.1:8080")
    args = p.parse_args()
    out: dict = {"base_url": args.base_url, "ok": True, "checks": []}
    try:
        with httpx.Client(timeout=10.0, trust_env=False) as client:
            for path in ("/health", "/ready", "/v1/llm/health", "/v1/graph/stats"):
                r = client.get(f"{args.base_url}{path}")
                item = {"path": path, "status": r.status_code}
                try:
                    item["body"] = r.json()
                except Exception:
                    item["body"] = r.text[:200]
                if r.status_code >= 400 and path != "/ready":
                    out["ok"] = False
                if path == "/ready" and r.status_code >= 400:
                    out["checks"].append({**item, "note": "ready degraded — expected if live strict without stores"})
                out["checks"].append(item)
            cfg = client.get(f"{args.base_url}/v1/llm/config", headers={"Authorization": "Bearer compliance"})
            out["llm_config"] = cfg.json() if cfg.status_code < 400 else {"status": cfg.status_code}
    except Exception as exc:
        out["ok"] = False
        out["error"] = f"{exc.__class__.__name__}: {exc}"
    print(json.dumps(out, ensure_ascii=False, indent=2))
    sys.exit(0 if out.get("ok") else 1)


if __name__ == "__main__":
    main()
