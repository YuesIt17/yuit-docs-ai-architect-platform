"""Export compiled LangGraph topology to Mermaid without live I/O.

Uses the same build_graph() factory as KnowledgeAgent with no-I/O doubles.
Does not call get_container(), MinIO, Neo4j, Qdrant, or LLM HTTP.
"""

from __future__ import annotations

import argparse
import socket
import sys
from pathlib import Path
from typing import Any

from normalize import normalize_mermaid
from paths import BACKEND, GEN_SOURCES, REPO_ROOT


class NetworkBlockedError(RuntimeError):
    pass


def _block_network() -> None:
    """Fail hard if anything tries to open a network connection."""

    def _deny(*_a, **_k):
        raise NetworkBlockedError("LangGraph export must not open network sockets")

    socket.socket.connect = _deny  # type: ignore[method-assign]
    socket.create_connection = _deny  # type: ignore[assignment]


class _DummyStore:
    def graph_resolve_doc_ids(self, *_a, **_k):
        return []

    def hybrid_retrieve(self, *_a, **_k):
        return []


class _DummyLLM:
    model_uri = "mock://export"

    async def complete(self, *_a, **_k):
        return ("", 0, 0)


def _ensure_backend_path() -> None:
    root = str(BACKEND)
    if root not in sys.path:
        sys.path.insert(0, root)


def export_mermaid(compiled: Any | None = None) -> str:
    """Return normalized Mermaid from a compiled graph (or build with doubles)."""
    _ensure_backend_path()
    if compiled is None:
        from kp.agent.graph import build_graph

        compiled = build_graph(_DummyStore(), _DummyLLM())
    raw = compiled.get_graph().draw_mermaid()
    # LangGraph emits graph TD; + HTML labels — normalize for Cursor preview + mmdc
    return normalize_mermaid(raw)


def graph_topology(compiled: Any | None = None) -> dict[str, Any]:
    """Normalized nodes/edges for consistency tests."""
    _ensure_backend_path()
    if compiled is None:
        from kp.agent.graph import build_graph

        compiled = build_graph(_DummyStore(), _DummyLLM())
    g = compiled.get_graph()
    nodes = sorted(str(n) for n in g.nodes)
    edges = sorted(
        (str(e.source), str(e.target), str(getattr(e, "data", "") or ""))
        for e in g.edges
    )
    return {"nodes": nodes, "edges": edges}


def write_export(out: Path | None = None, *, block_network: bool = True) -> Path:
    if block_network:
        _block_network()
    text = export_mermaid()
    target = out or (GEN_SOURCES / "agent-workflow.mmd")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    return target


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "-o",
        "--output",
        type=Path,
        default=GEN_SOURCES / "agent-workflow.mmd",
        help="Output .mmd path",
    )
    p.add_argument(
        "--allow-network",
        action="store_true",
        help="Do not monkey-patch sockets (debug only)",
    )
    args = p.parse_args(argv)
    write_export(args.output, block_network=not args.allow_network)
    print(f"wrote {args.output.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
