#!/usr/bin/env python3
"""Summarize counts from sec-ops JSON reports (Trivy, Semgrep, Checkov, ZAP)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

TRIVY_SEV = {"CRITICAL", "HIGH"}


def count_trivy(path: Path) -> tuple[int, int]:
    """Return (critical_high, total_vuln_or_misconfig)."""
    data = json.loads(path.read_text(encoding="utf-8"))
    high = 0
    total = 0
    for result in data.get("Results") or []:
        for vuln in result.get("Vulnerabilities") or []:
            total += 1
            if (vuln.get("Severity") or "").upper() in TRIVY_SEV:
                high += 1
        for mis in result.get("Misconfigurations") or []:
            total += 1
            if (mis.get("Severity") or "").upper() in TRIVY_SEV:
                high += 1
    return high, total


def count_semgrep(path: Path) -> int:
    data = json.loads(path.read_text(encoding="utf-8"))
    return len(data.get("results") or [])


def count_checkov(path: Path) -> tuple[int, int]:
    """Return (failed, passed) if summary present, else (failed_checks len, 0)."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "results" in data:
        summary = data.get("summary") or {}
        if summary:
            return int(summary.get("failed", 0)), int(summary.get("passed", 0))
        failed = data["results"].get("failed_checks") or []
        passed = data["results"].get("passed_checks") or []
        return len(failed), len(passed)
    # checkov multi-framework: list of reports
    if isinstance(data, list):
        failed = passed = 0
        for item in data:
            if not isinstance(item, dict):
                continue
            s = item.get("summary") or {}
            failed += int(s.get("failed", 0))
            passed += int(s.get("passed", 0))
        return failed, passed
    return 0, 0


def count_zap(path: Path) -> int:
    data = json.loads(path.read_text(encoding="utf-8"))
    site = data.get("site") or []
    n = 0
    for s in site:
        for alert in s.get("alerts") or []:
            n += 1
            _ = alert
    return n


def main() -> int:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("tmp/sec-ops")
    if not root.is_dir():
        print(f"[skip] not a directory: {root}", file=sys.stderr)
        return 2

    print(f"=== sec-ops summary: {root} ===")

    for path in sorted(root.glob("trivy-*.json")):
        try:
            high, total = count_trivy(path)
            print(f"Trivy {path.name}: CRITICAL/HIGH={high}  total_items={total}")
        except (json.JSONDecodeError, OSError) as exc:
            print(f"Trivy {path.name}: parse error ({exc})")

    sg = root / "semgrep.json"
    if sg.is_file():
        try:
            print(f"Semgrep: findings={count_semgrep(sg)}")
        except (json.JSONDecodeError, OSError) as exc:
            print(f"Semgrep: parse error ({exc})")

    for name in ("checkov.json", "results_json.json"):
        ck = root / name
        if ck.is_file():
            try:
                failed, passed = count_checkov(ck)
                print(f"Checkov {name}: failed={failed}  passed={passed}")
            except (json.JSONDecodeError, OSError) as exc:
                print(f"Checkov {name}: parse error ({exc})")
            break

    zap = root / "zap-baseline.json"
    if zap.is_file():
        try:
            print(f"ZAP baseline: alerts={count_zap(zap)}")
        except (json.JSONDecodeError, OSError) as exc:
            print(f"ZAP: parse error ({exc})")

    for label, name in (("Nmap", "nmap.txt"), ("Nuclei", "nuclei.txt"), ("kube-bench", "kube-bench.txt")):
        p = root / name
        if p.is_file():
            lines = p.read_text(encoding="utf-8", errors="replace").strip().splitlines()
            print(f"{label}: report_lines={len(lines)}  ({p.name})")

    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
