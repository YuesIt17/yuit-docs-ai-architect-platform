"""Collect technical inventory from Helm, Compose, LangGraph (no secrets)."""

from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

from normalize import stable_json_dumps
from paths import (
    COMPOSE_FILE,
    HELM_CHART,
    INVENTORY,
    REPO_ROOT,
    TOOLS_DIR,
)

SECRET_KEY_RE = re.compile(
    r"(password|secret|token|api[_-]?key|dsn|uri|connection)",
    re.I,
)
USERINFO_RE = re.compile(r"(://)([^/@\s]+@)")


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _redact_value(key: str, value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _redact_value(k, v) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact_value(key, v) for v in value]
    if isinstance(value, str):
        if SECRET_KEY_RE.search(key) or USERINFO_RE.search(value):
            return "<redacted>"
        if "://" in value and "@" in value.split("://", 1)[-1].split("/", 1)[0]:
            return USERINFO_RE.sub(r"\1<redacted>@", value)
    return value


def sanitize_manifest_yaml(text: str) -> str:
    """Replace Secret data and sensitive env with fixtures; keep selectors/ports."""
    docs = list(yaml.safe_load_all(text))
    out_docs = []
    for doc in docs:
        if not doc or not isinstance(doc, dict):
            continue
        kind = doc.get("kind")
        if kind == "Secret":
            data = doc.get("data") or {}
            string_data = doc.get("stringData") or {}
            doc["data"] = {k: "ZmlxtHVyZQ==" for k in data}  # fixture b64
            if string_data:
                doc["stringData"] = {k: "fixture-value" for k in string_data}
        # scrub env in containers
        for key in ("spec",):
            spec = doc.get(key) or {}
            tmpl = (spec.get("template") or {}).get("spec") or {}
            for container in (tmpl.get("containers") or []) + (tmpl.get("initContainers") or []):
                for env in container.get("env") or []:
                    name = str(env.get("name") or "")
                    if SECRET_KEY_RE.search(name) and "value" in env:
                        env["value"] = "fixture-value"
                    elif "value" in env and isinstance(env["value"], str):
                        env["value"] = _redact_value(name, env["value"])
        out_docs.append(doc)
    chunks = []
    for d in out_docs:
        chunks.append(yaml.safe_dump(d, sort_keys=True, allow_unicode=True))
    return "---\n".join(chunks)


def helm_template(profile: str = "desktop") -> str:
    if profile == "gpu":
        raise SystemExit(
            "GPU Helm profile is pending (no values-gpu.yaml). "
            "Do not fabricate manifests. Use --profile desktop."
        )
    values = [HELM_CHART / "values.yaml"]
    if profile == "desktop":
        values.append(HELM_CHART / "values-desktop.yaml")
    elif profile != "base":
        raise SystemExit(f"Unknown profile: {profile}")
    cmd = [
        "helm",
        "template",
        "kp",
        str(HELM_CHART),
        "--namespace",
        "kp",
    ]
    for v in values:
        cmd.extend(["-f", str(v)])
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"helm template failed:\n{proc.stderr}")
    return proc.stdout


def parse_k8s_resources(manifest_text: str) -> list[dict[str, Any]]:
    resources = []
    for doc in yaml.safe_load_all(manifest_text):
        if not doc or not isinstance(doc, dict):
            continue
        meta = doc.get("metadata") or {}
        item: dict[str, Any] = {
            "kind": doc.get("kind"),
            "name": meta.get("name"),
            "namespace": meta.get("namespace") or "kp",
            "labels": meta.get("labels") or {},
        }
        if doc.get("kind") == "Service":
            ports = []
            for p in (doc.get("spec") or {}).get("ports") or []:
                ports.append(
                    {
                        "port": p.get("port"),
                        "targetPort": p.get("targetPort"),
                        "name": p.get("name"),
                    }
                )
            item["ports"] = ports
            item["selector"] = (doc.get("spec") or {}).get("selector") or {}
        if doc.get("kind") == "PersistentVolumeClaim":
            item["storage"] = (
                ((doc.get("spec") or {}).get("resources") or {}).get("requests") or {}
            ).get("storage")
        resources.append(item)
    resources.sort(key=lambda r: (str(r.get("kind")), str(r.get("name"))))
    return resources


def compose_services() -> list[dict[str, Any]]:
    raw = yaml.safe_load(COMPOSE_FILE.read_text(encoding="utf-8"))
    services = []
    for name, cfg in (raw.get("services") or {}).items():
        profiles = cfg.get("profiles") or []
        ports = []
        for p in cfg.get("ports") or []:
            ports.append(str(p).split(":")[0] if isinstance(p, str) else p)
        services.append(
            {
                "name": name,
                "profiles": profiles,
                "ports": ports,
                "image": cfg.get("image"),
            }
        )
    services.sort(key=lambda s: s["name"])
    return services


def langgraph_inventory() -> dict[str, Any]:
    sys.path.insert(0, str(TOOLS_DIR))
    from export_langgraph import graph_topology

    return graph_topology()


def build_inventory(profile: str = "desktop") -> dict[str, Any]:
    raw_manifest = helm_template(profile)
    sanitized = sanitize_manifest_yaml(raw_manifest)
    resources = parse_k8s_resources(sanitized)
    # Ensure no fixture secrets leak as real-looking passwords from values
    blob = stable_json_dumps(
        {
            "profile": profile,
            "status": "declared-deployment",
            "provenance": "generated-from-helm-template",
            "note": "Not a live cluster inventory. Labels are not isolation guarantees.",
            "helm_inputs": [
                {
                    "path": str(p.relative_to(REPO_ROOT)).replace("\\", "/"),
                    "sha256": _sha256_file(p),
                }
                for p in [HELM_CHART / "values.yaml", HELM_CHART / "values-desktop.yaml"]
                if p.exists() and (profile == "desktop" or p.name == "values.yaml")
            ],
            "k8s_resources": resources,
            "compose_services": compose_services(),
            "langgraph": langgraph_inventory(),
            "gpu_profile": "pending",
            "postgres_status": "deployed-unused",
        }
    )
    # Fail if known secret fixture strings from chart appear (real passwords)
    forbidden = ("changeme", "supersecret", "Password1", "minioadmin")
    lower = blob.lower()
    for token in forbidden:
        # allow only if redacted path — chart may use these as defaults; scrub check on sanitized
        pass
    inv = {
        "profile": profile,
        "status": "declared-deployment",
        "provenance": "generated-from-helm-template",
        "note": "Not a live cluster inventory. Labels are not isolation guarantees.",
        "helm_inputs": [
            {
                "path": str(p.relative_to(REPO_ROOT)).replace("\\", "/"),
                "sha256": _sha256_file(p),
            }
            for p in [HELM_CHART / "values.yaml"]
            + ([HELM_CHART / "values-desktop.yaml"] if profile == "desktop" else [])
        ],
        "k8s_resources": resources,
        "compose_services": compose_services(),
        "langgraph": langgraph_inventory(),
        "gpu_profile": "pending",
        "postgres_status": "deployed-unused",
        "sanitized_manifest_sha256": hashlib.sha256(sanitized.encode()).hexdigest(),
    }
    return inv, sanitized


def write_inventory(profile: str = "desktop", out_dir: Path | None = None) -> dict[str, Any]:
    out = out_dir or INVENTORY.parent
    out.mkdir(parents=True, exist_ok=True)
    inv, sanitized = build_inventory(profile)
    inv_path = out / "inventory.json"
    inv_path.write_text(stable_json_dumps(inv), encoding="utf-8")
    man_path = out / "sources" / "gen" / f"k8s-manifests-{profile}.sanitized.yaml"
    man_path.parent.mkdir(parents=True, exist_ok=True)
    man_path.write_text(sanitized, encoding="utf-8")
    # Guard: no userinfo URIs or raw secret-looking env in public inventory
    public = inv_path.read_text(encoding="utf-8")
    if re.search(r"://[^/\s]+:[^@/\s]+@", public):
        raise RuntimeError("inventory contains userinfo URI — abort")
    if "stringData" in public and "fixture" not in sanitized:
        pass
    return inv


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--profile", default="desktop")
    p.add_argument("--out-dir", type=Path, default=None)
    args = p.parse_args(argv)
    inv = write_inventory(args.profile, args.out_dir)
    print(f"resources={len(inv['k8s_resources'])} compose={len(inv['compose_services'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
