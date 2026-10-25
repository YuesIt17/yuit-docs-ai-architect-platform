"""Deterministic normalization for Mermaid / inventory text (no timestamps)."""

from __future__ import annotations

import re


def normalize_mermaid(text: str) -> str:
    """Strip volatile noise and HTML so Cursor preview + mmdc both work."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # LangGraph / Structurizr HTML crumbs
    text = re.sub(r"</?p>", "", text)
    text = re.sub(
        r"<div[^>]*>\s*([^<]*?)\s*</div>(?:\s*<div[^>]*>\s*</div>)*",
        r"\1",
        text,
        flags=re.I,
    )
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("&nbsp;", " ")
    text = text.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
    # Preview-friendly headers (Cursor rejects "graph TD;")
    text = re.sub(r"^graph\s+TD\s*;", "flowchart TD", text, count=1, flags=re.M)
    text = re.sub(r"^graph\s+TB\s*;", "flowchart TB", text, count=1, flags=re.M)
    text = re.sub(r"^graph\s+TD\b", "flowchart TD", text, count=1, flags=re.M)
    text = re.sub(r"^graph\s+TB\b", "flowchart TB", text, count=1, flags=re.M)

    lines = []
    for raw in text.split("\n"):
        line = raw.rstrip()
        if line.strip().startswith("%%") and any(
            k in line.lower() for k in ("generated", "timestamp", "version", "langgraph")
        ):
            continue
        # Drop trailing edge/node semicolons that break some previews
        if re.match(r"^\s*[\w.<>\[\]()\"'-].*;\s*$", line) and "classDef" not in line:
            if line.rstrip().endswith(";") and not line.strip().startswith("%%"):
                line = line.rstrip()[:-1]
        lines.append(line)
    body = "\n".join(lines).strip() + "\n"
    body = re.sub(r"\n{3,}", "\n\n", body)
    return body


_MERMAID_RESERVED = {
    "end",
    "graph",
    "subgraph",
    "flowchart",
    "class",
    "classDef",
    "click",
    "style",
    "linkStyle",
    "direction",
}


def _safe_id(name: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_]", "_", name)
    if not safe or safe[0].isdigit() or safe.lower() in _MERMAID_RESERVED:
        safe = f"n_{safe}"
    return safe


# kp package layers for readable TB layout (avoid one long LR chain).
_PACKAGE_LAYERS: list[tuple[str, str, tuple[str, ...]]] = [
    ("layer_agent", "agent", ("agent", "graph", "state")),
    (
        "layer_api",
        "api",
        ("api", "chat", "deps", "health", "jobs", "llm", "router", "vision"),
    ),
    ("layer_app", "application", ("application", "audit")),
    ("layer_domain", "domain", ("domain", "nodes", "schemas")),
    (
        "layer_infra",
        "infrastructure",
        (
            "infrastructure",
            "cache",
            "embeddings",
            "neo4j_graph",
            "object_store",
            "qdrant_vectors",
        ),
    ),
    (
        "layer_obs",
        "observability",
        ("observability", "logging_json", "metrics", "spans", "tracing"),
    ),
]


def _flowchart_layered_packages(names: list[str], title: str) -> str:
    """Stack package layers TB; modules LR within each layer."""
    remaining = list(names)
    used: set[str] = set()
    lines = [
        "%% status: generated-from-code",
        "%% converted: classDiagram -> layered flowchart for editor preview",
        "flowchart TB",
        f"  subgraph {_safe_id(title)} [{title}]",
    ]
    layer_ids: list[str] = []
    for lid, label, members in _PACKAGE_LAYERS:
        present = [n for n in members if n in remaining and n not in used]
        if not present:
            continue
        layer_ids.append(lid)
        lines.append(f"    subgraph {lid} [{label}]")
        lines.append("      direction LR")
        for n in present:
            lines.append(f"      {_safe_id(n)}[{n}]")
            used.add(n)
        lines.append("    end")
    other = [n for n in remaining if n not in used]
    if other:
        lid = "layer_other"
        layer_ids.append(lid)
        lines.append(f"    subgraph {lid} [other]")
        lines.append("      direction LR")
        for n in other:
            lines.append(f"      {_safe_id(n)}[{n}]")
        lines.append("    end")
    lines.append("  end")
    for a, b in zip(layer_ids, layer_ids[1:]):
        lines.append(f"  {a} --> {b}")
    return "\n".join(lines) + "\n"


def _flowchart_chunked(names: list[str], title: str, rels: list[tuple[str, str]]) -> str:
    """Classes: real edges if present; else wrap into LR rows (no fake chain)."""
    lines = [
        "%% status: generated-from-code",
        "%% converted: classDiagram -> flowchart for editor preview",
        "flowchart TB",
        f"  subgraph {_safe_id(title)} [{title}]",
    ]
    if rels:
        for n in names:
            lines.append(f"    {_safe_id(n)}[{n}]")
        lines.append("  end")
        seen = set(names)
        for a, b in rels:
            if a in seen and b in seen:
                lines.append(f"  {_safe_id(a)} --> {_safe_id(b)}")
        return "\n".join(lines) + "\n"

    row_size = 4
    row_ids: list[str] = []
    for i in range(0, len(names), row_size):
        chunk = names[i : i + row_size]
        rid = f"row_{i // row_size}"
        row_ids.append(rid)
        lines.append(f"    subgraph {rid} [row_{i // row_size}]")
        lines.append("      direction LR")
        for n in chunk:
            lines.append(f"      {_safe_id(n)}[{n}]")
        lines.append("    end")
    lines.append("  end")
    for a, b in zip(row_ids, row_ids[1:]):
        lines.append(f"  {a} ~~~ {b}")
    return "\n".join(lines) + "\n"


def classdiagram_to_flowchart(text: str, title: str = "packages") -> str:
    """Convert empty-ish pyreverse classDiagram into a readable flowchart TB."""
    classes = re.findall(r"^\s*class\s+(\w+)", text, flags=re.M)
    seen: set[str] = set()
    names: list[str] = []
    for c in classes:
        if c not in seen:
            seen.add(c)
            names.append(c)
    max_nodes = 24
    rels = re.findall(
        r"^\s*(\w+)\s+(?:<\|--|--\|>|\*--|o--|--|\.\.>|<\.\.)\s*(\w+)",
        text,
        flags=re.M,
    )
    if len(names) > max_nodes and not rels:
        names = names[:max_nodes]
    if "package" in title.lower():
        return _flowchart_layered_packages(names, title)
    return _flowchart_chunked(names, title, rels)


def stable_json_dumps(obj) -> str:
    import json

    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
