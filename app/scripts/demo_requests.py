#!/usr/bin/env python3
"""Fixed demo questions per role — safe educational seed only."""

from __future__ import annotations

import argparse
import json
import sys

import httpx

CASES = [
    {
        "id": "graph_allergen",
        "token": "associate",
        "message": "Какие политики маркировки связаны с gluten?",
        "expect": "citations or grounded answer",
    },
    {
        "id": "acl_manager_secret",
        "token": "manager",
        "message": "Расскажи про Q4 Closed Promo Margin Playbook и маржу 42%",
        "expect": "no secret citations / no 42%",
    },
    {
        "id": "acl_compliance_secret",
        "token": "compliance",
        "message": "Расскажи про Q4 Closed Promo Margin Playbook",
        "expect": "may cite secret if seeded",
    },
    {
        "id": "refuse_irrelevant",
        "token": "associate",
        "message": "квантовая физика чёрных дыр xyzzy",
        "expect": "insufficient context refusal",
    },
    {
        "id": "guest_public_only",
        "token": "guest",
        "message": "Что такое FreshFarm oats?",
        "expect": "public-only or empty",
    },
]


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--base-url", default="http://127.0.0.1:8080")
    p.add_argument("--case", default=None, help="Run a single case id")
    args = p.parse_args()
    cases = [c for c in CASES if args.case is None or c["id"] == args.case]
    results = []
    with httpx.Client(timeout=60.0, trust_env=False) as client:
        for case in cases:
            r = client.post(
                f"{args.base_url}/v1/chat",
                headers={"Authorization": f"Bearer {case['token']}"},
                json={"message": case["message"], "stream": False},
            )
            body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
            results.append(
                {
                    "id": case["id"],
                    "http": r.status_code,
                    "expect": case["expect"],
                    "acl_decision": body.get("acl_decision"),
                    "citations": body.get("citations"),
                    "answer_preview": (body.get("answer") or "")[:240],
                    "request_id": body.get("request_id"),
                }
            )
    print(json.dumps(results, ensure_ascii=False, indent=2))
    sys.exit(0 if all(x["http"] < 500 for x in results) else 1)


if __name__ == "__main__":
    main()
