"""Consistency checks: source-map symbols, inventory drift, secret leakage."""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml

from paths import BACKEND, GEN_IMAGES, GEN_SOURCES, INVENTORY, REPO_ROOT, SOURCE_MAP

SECRET_PATTERNS = [
    re.compile(r"://[^/\s]+:[^@/\s]+@"),  # userinfo in URI
    re.compile(r"(?i)(password|secret|api[_-]?key)\s*[:=]\s*['\"][^'\"]{8,}"),
]


def _load_source_map() -> dict[str, Any]:
    if not SOURCE_MAP.exists():
        raise FileNotFoundError(f"missing source-map: {SOURCE_MAP}")
    return yaml.safe_load(SOURCE_MAP.read_text(encoding="utf-8"))


def _symbol_exists(module_path: str, symbol: str | None) -> bool:
    """Check that a Python file exists and optionally defines symbol (class/func/assign)."""
    path = REPO_ROOT / module_path
    if not path.exists():
        return False
    if not symbol:
        return True
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name == symbol:
                return True
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == symbol:
                    return True
    return False


def check_source_map() -> list[str]:
    errors: list[str] = []
    sm = _load_source_map()
    for el in sm.get("elements") or []:
        eid = el.get("id")
        status = el.get("status", "current")
        src = el.get("source") or {}
        path = src.get("path")
        symbol = src.get("symbol")
        if status in ("current", "curated-from-code", "generated-from-code") and path:
            if path.endswith(".py") and not _symbol_exists(path, symbol):
                errors.append(f"source-map {eid}: missing {path}::{symbol or '<file>'}")
        if status == "current" and el.get("runtime") == "required-missing":
            errors.append(f"source-map {eid}: current element marked required-missing")
    return errors


def check_inventory_langgraph() -> list[str]:
    errors: list[str] = []
    if not INVENTORY.exists():
        return ["inventory.json missing — run extract_inventory / build first"]
    inv = json.loads(INVENTORY.read_text(encoding="utf-8"))
    nodes = set((inv.get("langgraph") or {}).get("nodes") or [])
    expected = {
        "guard_input",
        "route",
        "graph_retrieve",
        "vector_retrieve",
        "refine_retrieve",
        "label_recognize",
        "policy_check",
        "synthesize",
        "guard_output",
        "__start__",
        "__end__",
    }
    # LangGraph may name start/end differently across versions
    missing = {n for n in expected if n not in nodes and not n.startswith("__")}
    if missing:
        errors.append(f"langgraph inventory missing nodes: {sorted(missing)}")
    return errors


def check_k8s_mapping() -> list[str]:
    errors: list[str] = []
    if not INVENTORY.exists():
        return errors
    inv = json.loads(INVENTORY.read_text(encoding="utf-8"))
    sm = _load_source_map()
    resource_names = {
        (r.get("kind"), r.get("name")) for r in inv.get("k8s_resources") or []
    }
    for el in sm.get("elements") or []:
        k8s = el.get("k8s")
        if not k8s:
            continue
        if el.get("status") in ("target", "pending"):
            continue
        key = (k8s.get("kind"), k8s.get("name"))
        if key not in resource_names:
            errors.append(f"source-map {el.get('id')}: k8s {key} not in inventory")
    return errors


def check_secrets_in_outputs(root: Path | None = None) -> list[str]:
    errors: list[str] = []
    base = root or (INVENTORY.parent)
    for path in list(base.rglob("*.json")) + list(base.rglob("*.svg")) + list(
        base.rglob("*.mmd")
    ):
        if "sanitized" in path.name:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pat in SECRET_PATTERNS:
            if pat.search(text):
                errors.append(f"possible secret in {path.relative_to(REPO_ROOT)}")
                break
    return errors


def check_expected_outputs() -> list[str]:
    errors: list[str] = []
    expected_mmd = [
        "agent-workflow.mmd",
        "python-packages.mmd",
        "c4-context.mmd",
        "c4-container.mmd",
        "c4-backend-components.mmd",
        "current-hybrid-deployment.mmd",
        "target-overview.mmd",
        "sequence-chat.mmd",
        "data-flow.mmd",
        "er-conceptual.mmd",
        "k8s-topology-desktop.mmd",
    ]
    expected_svg = [p.replace(".mmd", ".svg") for p in expected_mmd] + [
        "python-classes-agent.svg",
        "python-classes-stores.svg",
        "k8s-topology-desktop-kube.svg",
    ]
    for name in expected_mmd:
        if not (GEN_SOURCES / name).exists():
            errors.append(f"missing generated source: {name}")
    for name in expected_svg:
        if not (GEN_IMAGES / name).exists():
            errors.append(f"missing generated image: {name}")
    return errors


def run_all(*, include_outputs: bool = True) -> list[str]:
    errors: list[str] = []
    errors.extend(check_source_map())
    errors.extend(check_inventory_langgraph())
    errors.extend(check_k8s_mapping())
    errors.extend(check_secrets_in_outputs())
    if include_outputs:
        errors.extend(check_expected_outputs())
    return errors


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--skip-outputs", action="store_true")
    args = p.parse_args(argv)
    errors = run_all(include_outputs=not args.skip_outputs)
    if errors:
        print("CONSISTENCY FAIL:")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("consistency OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
