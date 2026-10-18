#!/usr/bin/env python3
"""Print CRITICAL/HIGH findings from a Trivy JSON report (image or config)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

SEVERITIES = {"CRITICAL", "HIGH"}


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: sec-parse-trivy.py <trivy.json> [trivy.json ...]", file=sys.stderr)
        return 2

    total = 0
    for arg in sys.argv[1:]:
        path = Path(arg)
        if not path.is_file():
            print(f"[skip] not found: {path}")
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        results = data.get("Results") or []
        print(f"=== {path.name} ===")
        file_count = 0
        for result in results:
            target = result.get("Target", "?")
            for vuln in result.get("Vulnerabilities") or []:
                sev = (vuln.get("Severity") or "").upper()
                if sev not in SEVERITIES:
                    continue
                file_count += 1
                vid = vuln.get("VulnerabilityID", "?")
                pkg = vuln.get("PkgName", "?")
                title = (vuln.get("Title") or vuln.get("Description") or "")[:80]
                print(f"  [{sev}] {vid}  {pkg}  {target}")
                if title:
                    print(f"         {title}")
            for mis in result.get("Misconfigurations") or []:
                sev = (mis.get("Severity") or "").upper()
                if sev not in SEVERITIES:
                    continue
                file_count += 1
                mid = mis.get("ID", "?")
                title = mis.get("Title", "")
                print(f"  [{sev}] {mid}  {target}")
                if title:
                    print(f"         {title}")
        if file_count == 0:
            print("  (no CRITICAL/HIGH)")
        total += file_count
        print()

    print(f"Total CRITICAL/HIGH: {total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
