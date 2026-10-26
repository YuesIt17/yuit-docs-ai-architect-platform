#!/usr/bin/env python3
"""Unified diagrams build / check / bootstrap.

Windows (no make):
  python tools/diagrams/build.py --bootstrap
  python tools/diagrams/build.py --profile desktop
  python tools/diagrams/build.py --profile desktop --check
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from paths import (
    BACKEND,
    GENERATED,
    MERMAID_CONFIG,
    MODEL,
    REPO_ROOT,
    SRC_GEN,
    SRC_MANUAL,
    TOOLS_DIR,
)

MANUAL_MMD = (
    "c4-context.mmd",
    "c4-container.mmd",
    "c4-backend-components.mmd",
    "current-hybrid-deployment.mmd",
    "target-overview.mmd",
    "sequence-chat.mmd",
    "data-flow.mmd",
    "er-conceptual.mmd",
)

GEN_STABLE_MMD = (
    "agent-workflow.mmd",
    "k8s-topology-desktop.mmd",
)

# Ensure sibling imports work when invoked as a script.
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))


def _run(cmd: list[str], *, cwd: Path | None = None, env: dict | None = None) -> None:
    print("+", " ".join(cmd))
    proc = subprocess.run(cmd, cwd=cwd or REPO_ROOT, env=env, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"command failed ({proc.returncode}): {' '.join(cmd)}")


def _which(name: str) -> str | None:
    return shutil.which(name)


def _venv_python() -> Path:
    win = BACKEND / ".venv" / "Scripts" / "python.exe"
    unix = BACKEND / ".venv" / "bin" / "python"
    if win.exists():
        return win
    if unix.exists():
        return unix
    return Path(sys.executable)


def _fix_kube_diagrams_windows_layout() -> None:
    """KubeDiagrams wheel puts data in venv/bin but script in Scripts/ on Windows."""
    venv = BACKEND / ".venv"
    data_src = venv / "bin"
    scripts = venv / "Scripts"
    if not data_src.exists() or not scripts.exists():
        return
    for name in ("kube-diagrams.yaml",):
        src = data_src / name
        dst = scripts / name
        if src.exists() and not dst.exists():
            shutil.copy2(src, dst)
    icons_src = data_src / "icons"
    icons_dst = scripts / "icons"
    if icons_src.exists() and not icons_dst.exists():
        shutil.copytree(icons_src, icons_dst)


def bootstrap() -> None:
    """Install pinned local toolchain (npm + pip). Docker pull is optional."""
    npm = _which("npm")
    if not npm:
        raise RuntimeError("npm required for Mermaid CLI bootstrap")
    _run([npm, "install"], cwd=TOOLS_DIR)
    py = _venv_python()
    _run([str(py), "-m", "pip", "install", "-r", str(TOOLS_DIR / "requirements.txt")])
    _fix_kube_diagrams_windows_layout()
    # Optional Docker pulls
    if _which("docker"):
        try:
            _run(
                [
                    "docker",
                    "pull",
                    "structurizr/cli:2025.05.28",
                ]
            )
        except RuntimeError as exc:
            print(f"WARN: structurizr pull skipped: {exc}")
    print("bootstrap OK")


def _mmdc() -> list[str]:
    local = TOOLS_DIR / "node_modules" / ".bin" / ("mmdc.cmd" if os.name == "nt" else "mmdc")
    if local.exists():
        return [str(local)]
    w = _which("mmdc")
    if w:
        return [w]
    raise RuntimeError("mmdc not found — run build.py --bootstrap")


def render_mermaid(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = _mmdc() + [
        "-i",
        str(src),
        "-o",
        str(dest),
        "-c",
        str(MERMAID_CONFIG),
        "-b",
        "transparent",
    ]
    # Prefer local Chromium/Edge if puppeteer chrome missing — mmdc bundles chromium usually.
    _run(cmd)


def _gen_dir(out_dir: Path) -> Path:
    d = out_dir / "sources" / "gen"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _manual_dir(out_dir: Path) -> Path:
    """Committed manual sources live under architecture/diagrams; copy into temp builds."""
    committed = SRC_MANUAL
    dest = out_dir / "sources" / "manual"
    if dest.resolve() == committed.resolve():
        return dest
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(committed, dest)
    return dest


def export_langgraph(out_dir: Path) -> None:
    from export_langgraph import write_export

    write_export(_gen_dir(out_dir) / "agent-workflow.mmd", block_network=True)


def export_pyreverse(out_dir: Path) -> None:
    py = _venv_python()
    tmp = out_dir / "tmp_pyreverse"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    env = os.environ.copy()
    env["PYTHONPATH"] = str(BACKEND)
    # Package diagram
    pyreverse = BACKEND / ".venv" / "Scripts" / "pyreverse.exe"
    if not pyreverse.exists():
        pyreverse = BACKEND / ".venv" / "bin" / "pyreverse"
    pyr_cmd = [str(pyreverse)] if pyreverse.exists() else [str(py), "-m", "pylint.pyreverse.main"]
    _run(
        [
            *pyr_cmd,
            "-o",
            "mmd",
            "-p",
            "kp",
            "-d",
            str(tmp),
            "--ignore",
            "tests",
            "kp.agent",
            "kp.application",
            "kp.repositories",
            "kp.infrastructure",
            "kp.security",
            "kp.deps",
            "kp.domain",
            "kp.api",
            "kp.observability",
        ],
        cwd=BACKEND,
        env=env,
    )
    # pyreverse names files packages_kp.mmd / classes_kp.mmd
    packages = list(tmp.glob("packages*.mmd"))
    src_dir = _gen_dir(out_dir)
    from normalize import classdiagram_to_flowchart, normalize_mermaid

    if packages:
        raw = packages[0].read_text(encoding="utf-8")
        (src_dir / "python-packages.mmd").write_text(
            normalize_mermaid(classdiagram_to_flowchart(raw, "kp_packages")),
            encoding="utf-8",
        )
    else:
        raise RuntimeError("pyreverse did not produce packages*.mmd")

    # Focused class views via filtered modules
    for label, modules in (
        ("agent", ["kp.agent.graph", "kp.agent.state", "kp.security.guardrails", "kp.security.rbac"]),
        (
            "stores",
            [
                "kp.repositories.hybrid_store",
                "kp.repositories.memory_store",
                "kp.repositories.protocols",
                "kp.infrastructure.neo4j_graph",
                "kp.infrastructure.qdrant_vectors",
                "kp.infrastructure.object_store",
            ],
        ),
    ):
        focus = tmp / label
        focus.mkdir(exist_ok=True)
        _run(
            [
                *pyr_cmd,
                "-o",
                "mmd",
                "-p",
                label,
                "-d",
                str(focus),
                *modules,
            ],
            cwd=BACKEND,
            env=env,
        )
        cls = list(focus.glob("classes*.mmd"))
        if cls:
            raw = cls[0].read_text(encoding="utf-8")
            (src_dir / f"python-classes-{label}.mmd").write_text(
                normalize_mermaid(classdiagram_to_flowchart(raw, f"kp_{label}")),
                encoding="utf-8",
            )
    shutil.rmtree(tmp, ignore_errors=True)


def validate_structurizr() -> None:
    """Validate Structurizr DSL. Mermaid C4 views live in sources/manual (not DSL export)."""
    workspace = MODEL / "workspace.dsl"
    if not workspace.exists():
        raise RuntimeError(f"missing {workspace}")

    dsl = MODEL / "workspace.dsl"
    dsl.write_text(
        dsl.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n"),
        encoding="utf-8",
    )

    docker = _which("docker")
    if docker:
        vol = str(REPO_ROOT).replace("\\", "/")
        try:
            _run(
                [
                    docker,
                    "run",
                    "--rm",
                    "-v",
                    f"{vol}:/workspace",
                    "-w",
                    "/workspace",
                    "structurizr/cli:2025.05.28",
                    "validate",
                    "-workspace",
                    "architecture/diagrams/model/workspace.dsl",
                ]
            )
        except RuntimeError as exc:
            print(f"WARN: Structurizr validate failed ({exc})")


def ensure_manual_sources(out_dir: Path) -> Path:
    """Ensure sources/manual exists (copy into temp builds) and required files are present."""
    manual = _manual_dir(out_dir)
    for name in MANUAL_MMD:
        path = manual / name
        if not path.exists():
            raise RuntimeError(f"missing manual Mermaid view {path}")
    return manual


def _kube_diagram_input(sanitized: Path, diagram_yaml: Path) -> None:
    """Strip NetworkPolicy (and similar edge noise) so Graphviz layout stays readable."""
    import yaml

    skip_kinds = {"NetworkPolicy"}
    docs: list[dict] = []
    for doc in yaml.safe_load_all(sanitized.read_text(encoding="utf-8")):
        if not doc or not isinstance(doc, dict):
            continue
        if doc.get("kind") in skip_kinds:
            continue
        docs.append(doc)
    chunks = [yaml.safe_dump(d, sort_keys=True, allow_unicode=True) for d in docs]
    diagram_yaml.write_text("---\n".join(chunks), encoding="utf-8")


def _ensure_svg_icons_embedded(svg_path: Path) -> None:
    """Re-embed any remaining remote/broken icon hrefs from local diagrams package."""
    import base64
    import re

    text = svg_path.read_text(encoding="utf-8")
    if "raw.githubusercontent.com" not in text and "xlink:href=\"http" not in text:
        if "data:image" in text:
            return
    try:
        import diagrams as diagrams_pkg
    except ImportError as exc:
        raise RuntimeError("diagrams package required to embed k8s icons") from exc

    resources = Path(diagrams_pkg.__file__).resolve().parent.parent / "resources"
    pattern = re.compile(r'xlink:href="([^"]+)"')

    def repl(match: re.Match[str]) -> str:
        href = match.group(1)
        if href.startswith("data:"):
            return match.group(0)
        # GitHub URL may contain Windows backslashes from KubeDiagrams post-process
        normalized = href.replace("\\", "/")
        local: Path | None = None
        for marker in ("/resources/", "resources/"):
            idx = normalized.find(marker)
            if idx >= 0:
                rel = normalized[idx + len("resources/") :].lstrip("/")
                candidate = resources / rel.replace("/", os.sep)
                if candidate.exists():
                    local = candidate
                    break
        if local is None:
            # Absolute path left by Graphviz
            cand = Path(href)
            if cand.exists():
                local = cand
        if local is None or not local.exists():
            print(f"WARN: k8s icon not found for {href}")
            return match.group(0)
        b64 = base64.b64encode(local.read_bytes()).decode("ascii")
        return f'xlink:href="data:image/png;base64,{b64}"'

    new_text = pattern.sub(repl, text)
    svg_path.write_text(new_text, encoding="utf-8")


def _k8s_topology_mermaid(resources: list[dict], profile: str) -> str:
    """Readable Helm topology for Cursor/GitHub — Graphviz KubeDiagrams stays as .kube.svg."""
    from normalize import normalize_mermaid, _safe_id

    deploys = [r for r in resources if r.get("kind") == "Deployment"]
    svc_names = {r["name"] for r in resources if r.get("kind") == "Service"}
    pvcs = [r for r in resources if r.get("kind") == "PersistentVolumeClaim"]
    ings = [r for r in resources if r.get("kind") == "Ingress"]

    lines = [
        "%% status: generated-from-helm",
        f"%% profile: {profile}",
        "%% note: Declared Helm topology not live cluster. NetworkPolicy omitted.",
        "flowchart TB",
        "  subgraph ns_kp [Namespace_kp]",
    ]
    for d in deploys:
        name = str(d.get("name") or "unknown")
        did = _safe_id(f"dep_{name}")
        lines.append(f"    {did}[Deploy_{name}]")
        if name in svc_names:
            sid = _safe_id(f"svc_{name}")
            lines.append(f"    {sid}[Svc_{name}]")
            lines.append(f"    {sid} --> {did}")
    for pvc in pvcs:
        name = str(pvc.get("name") or "unknown")
        lines.append(f"    {_safe_id(f'pvc_{name}')}[(PVC_{name})]")
    for ing in ings:
        name = str(ing.get("name") or "unknown")
        lines.append(f"    {_safe_id(f'ing_{name}')}[Ingress_{name}]")
    if any(r.get("kind") == "Secret" for r in resources):
        lines.append("    secret_kp[Secret_kp_secrets]")
    lines.append("  end")

    # Ingress → Service (chart naming)
    for ing_name, svc_name in (("kp-api", "api"), ("kp-ui", "frontend")):
        if any(i.get("name") == ing_name for i in ings) and svc_name in svc_names:
            lines.append(
                f"  {_safe_id(f'ing_{ing_name}')} --> {_safe_id(f'svc_{svc_name}')}"
            )
    for pvc_name, dep_name in (
        ("kp-minio-data", "minio"),
        ("kp-neo4j-data", "neo4j"),
        ("kp-postgres-data", "postgres"),
        ("kp-qdrant-data", "qdrant"),
    ):
        if any(p.get("name") == pvc_name for p in pvcs) and any(
            d.get("name") == dep_name for d in deploys
        ):
            lines.append(
                f"  {_safe_id(f'dep_{dep_name}')} --> {_safe_id(f'pvc_{pvc_name}')}"
            )
    return normalize_mermaid("\n".join(lines) + "\n")


def export_kube_diagrams(out_dir: Path, profile: str) -> None:
    from extract_inventory import write_inventory

    _fix_kube_diagrams_windows_layout()
    inv = write_inventory(profile, out_dir)
    gen = _gen_dir(out_dir)
    man = gen / f"k8s-manifests-{profile}.sanitized.yaml"
    diagram_in = gen / f"k8s-manifests-{profile}.diagram.yaml"
    _kube_diagram_input(man, diagram_in)

    # Canonical readable view (Mermaid) — opens cleanly in Cursor without remote icons
    mmd_path = gen / f"k8s-topology-{profile}.mmd"
    mmd_path.write_text(
        _k8s_topology_mermaid(inv.get("k8s_resources") or [], profile),
        encoding="utf-8",
    )

    # KubeDiagrams artifact (embedded icons); keep beside Mermaid SVG
    images = out_dir / "images"
    images.mkdir(parents=True, exist_ok=True)
    # Do not put a fake extension in -o: KubeDiagrams treats the last suffix as format.
    out_stem = images / f"k8s-topology-{profile}-kube"
    py = _venv_python()
    script = BACKEND / ".venv" / "Scripts" / "kube-diagrams"
    if not script.exists():
        script = BACKEND / ".venv" / "bin" / "kube-diagrams"
    if not script.exists():
        found = _which("kube-diagrams")
        if not found:
            raise RuntimeError("kube-diagrams not found — run build.py --bootstrap")
        script = Path(found)
    _run(
        [
            str(py),
            str(script),
            "-f",
            "svg",
            "--embed-all-icons",
            "-o",
            str(out_stem),
            str(diagram_in),
        ]
    )
    kube_svg = Path(str(out_stem) + ".svg")
    if not kube_svg.exists():
        raise RuntimeError(f"KubeDiagrams did not produce SVG at {kube_svg}")
    _ensure_svg_icons_embedded(kube_svg)


def render_all_mermaid(out_dir: Path) -> list[str]:
    images = out_dir / "images"
    images.mkdir(parents=True, exist_ok=True)
    rendered = []
    roots = [
        out_dir / "sources" / "gen",
        out_dir / "sources" / "manual",
    ]
    for root in roots:
        if not root.exists():
            continue
        for mmd in sorted(root.glob("*.mmd")):
            if "manifest" in mmd.name:
                continue
            dest = images / (mmd.stem + ".svg")
            try:
                render_mermaid(mmd, dest)
                rendered.append(dest.name)
            except RuntimeError as exc:
                print(f"WARN: mermaid render failed for {mmd.name}: {exc}")
                raise
    return rendered


def write_provenance(out_dir: Path, profile: str, outputs: list[str]) -> None:
    # No commit SHA in tracked comparison file content that would cause loops —
    # store dirty tip only as optional non-compared field when env CI sets it.
    tools = {
        "mermaid_cli": "@mermaid-js/mermaid-cli@11.4.2",
        "pylint": "3.3.7",
        "structurizr_cli_image": "structurizr/cli:2025.05.28",
        "kube_diagrams": "0.5.0",
    }
    data = {
        "profile": profile,
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tools": tools,
        "outputs": sorted(outputs),
        "origin_levels": {
            "generated-from-code": [
                "agent-workflow",
                "python-packages",
                "python-classes-agent",
                "python-classes-stores",
                "k8s-topology-desktop",
            ],
            "curated-from-code": [
                "c4-context",
                "c4-container",
                "c4-backend-components",
                "current-hybrid-deployment",
                "sequence-chat",
                "data-flow",
            ],
            "target-design": ["target-overview", "er-conceptual"],
        },
        "limitations": [
            "sources/gen = codegen; sources/manual = hand-edited Mermaid.",
            "k8s-topology-*.svg is Mermaid from Helm inventory; *-kube.svg is KubeDiagrams with embedded icons.",
            "KubeDiagrams / Mermaid show declared Helm topology, not live cluster state.",
            "Structurizr Mermaid export does not preserve all native renderer features.",
            "Pyreverse is static analysis; dynamic DI wiring may be incomplete.",
            "Postgres is deployed-unused; ER is intended schema from init.sql.",
            "GPU/vLLM Helm profile is pending.",
        ],
    }
    if os.environ.get("DIAGRAMS_INCLUDE_GIT_SHA") == "1":
        try:
            sha = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True
            ).strip()
            data["git_sha_ci_only"] = sha
        except Exception:
            pass
    (out_dir / "provenance.json").write_text(
        json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def build(profile: str, out_dir: Path) -> None:
    if profile == "gpu":
        raise SystemExit(
            "GPU profile pending: no values-gpu.yaml. Refusing to fabricate manifests."
        )
    if out_dir.exists() and out_dir.resolve() != GENERATED.resolve():
        shutil.rmtree(out_dir)
    (out_dir / "sources" / "gen").mkdir(parents=True, exist_ok=True)
    (out_dir / "images").mkdir(parents=True, exist_ok=True)

    ensure_manual_sources(out_dir)
    export_langgraph(out_dir)
    export_pyreverse(out_dir)
    validate_structurizr()
    export_kube_diagrams(out_dir, profile)
    rendered = render_all_mermaid(out_dir)
    outputs: list[str] = []
    for sub in ("gen", "manual"):
        d = out_dir / "sources" / sub
        if d.exists():
            outputs.extend(f"{sub}/{p.name}" for p in d.iterdir())
    outputs.extend(p.name for p in (out_dir / "images").iterdir())
    write_provenance(out_dir, profile, outputs)
    print(f"build OK profile={profile} mermaid_svgs={len(rendered)}")


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(profile: str) -> int:
    """Regenerate gen/ to temp; compare with committed sources/gen + inventory; do not overwrite."""
    with tempfile.TemporaryDirectory(prefix="kp-diagrams-") as tmp:
        tmp_path = Path(tmp) / "generated"
        build(profile, tmp_path)
        errors: list[str] = []
        committed_gen = SRC_GEN
        temp_gen = tmp_path / "sources" / "gen"
        if not committed_gen.exists():
            errors.append("committed architecture/diagrams/sources/gen missing")
        else:
            for name in GEN_STABLE_MMD:
                tfile = temp_gen / name
                cfile = committed_gen / name
                if not tfile.exists():
                    errors.append(f"missing regenerated gen source: {name}")
                    continue
                if not cfile.exists():
                    errors.append(f"missing committed gen source: {name}")
                    continue
                if tfile.read_text(encoding="utf-8") != cfile.read_text(encoding="utf-8"):
                    errors.append(f"stale gen source (drift): {name}")
            for tfile in temp_gen.glob("*.mmd"):
                if not (committed_gen / tfile.name).exists():
                    errors.append(f"missing committed gen source: {tfile.name}")
            for name in MANUAL_MMD:
                if not (SRC_MANUAL / name).exists():
                    errors.append(f"missing committed manual source: {name}")
        # inventory
        c_inv = GENERATED / "inventory.json"
        t_inv = tmp_path / "inventory.json"
        if c_inv.exists() and t_inv.exists():
            cj = json.loads(c_inv.read_text(encoding="utf-8"))
            tj = json.loads(t_inv.read_text(encoding="utf-8"))
            for volatile in ("sanitized_manifest_sha256",):
                cj.pop(volatile, None)
                tj.pop(volatile, None)
            if cj.get("k8s_resources") != tj.get("k8s_resources"):
                errors.append("inventory k8s_resources drift")
            if cj.get("langgraph") != tj.get("langgraph"):
                errors.append("inventory langgraph drift")
        else:
            errors.append("inventory.json missing in committed or temp output")

        from check_consistency import run_all

        errors.extend(run_all(include_outputs=True))

        if errors:
            print("CHECK FAIL:")
            for e in errors:
                print(f"  - {e}")
            return 1
    print("check OK")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--bootstrap", action="store_true")
    p.add_argument("--profile", default="desktop")
    p.add_argument("--check", action="store_true")
    p.add_argument(
        "--out",
        type=Path,
        default=GENERATED,
        help="Output directory (default architecture/diagrams)",
    )
    args = p.parse_args(argv)
    os.chdir(REPO_ROOT)
    if args.bootstrap:
        bootstrap()
        return 0
    if args.check:
        return check(args.profile)
    build(args.profile, args.out)
    from check_consistency import run_all

    errs = run_all(include_outputs=True)
    if errs:
        print("POST-BUILD CONSISTENCY WARN/FAIL:")
        for e in errs:
            print(f"  - {e}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
