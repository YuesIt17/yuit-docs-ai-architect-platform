"""Architecture tests: LangGraph export is no-I/O, deterministic, topology-accurate."""

from __future__ import annotations

import socket
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
TOOLS = REPO / "tools" / "diagrams"
BACKEND = REPO / "app" / "backend"
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(BACKEND))

from export_langgraph import (  # noqa: E402
    NetworkBlockedError,
    _DummyLLM,
    _DummyStore,
    export_mermaid,
    graph_topology,
)
from kp.agent.graph import build_graph  # noqa: E402
from normalize import normalize_mermaid  # noqa: E402


def test_export_deterministic():
    a = export_mermaid()
    b = export_mermaid()
    assert a == b
    assert normalize_mermaid(a) == a


def test_topology_matches_compiled_graph():
    topo = graph_topology()
    nodes = set(topo["nodes"])
    for required in (
        "guard_input",
        "route",
        "graph_retrieve",
        "vector_retrieve",
        "refine_retrieve",
        "label_recognize",
        "policy_check",
        "synthesize",
        "guard_output",
    ):
        assert required in nodes


def test_topology_change_changes_export():
    from langgraph.graph import END, StateGraph
    from typing_extensions import TypedDict

    class S(TypedDict, total=False):
        x: int

    g = StateGraph(S)
    g.add_node("a", lambda s: s)
    g.add_node("b", lambda s: s)
    g.set_entry_point("a")
    g.add_edge("a", "b")
    g.add_edge("b", END)
    compiled = g.compile()
    base = export_mermaid()
    other = normalize_mermaid(compiled.get_graph().draw_mermaid())
    assert other != base
    assert "a" in other and "b" in other


def test_network_blocked_during_write_export(tmp_path, monkeypatch):
    from export_langgraph import write_export

    def boom(*_a, **_k):
        raise NetworkBlockedError("blocked")

    monkeypatch.setattr(socket.socket, "connect", boom)
    out = tmp_path / "agent-workflow.mmd"
    write_export(out, block_network=True)
    text = out.read_text(encoding="utf-8")
    assert "guard_input" in text
    with pytest.raises(NetworkBlockedError):
        socket.socket().connect(("127.0.0.1", 1))  # type: ignore[call-arg]


def test_build_graph_same_as_agent():
    store, llm = _DummyStore(), _DummyLLM()
    from kp.agent.graph import KnowledgeAgent

    agent = KnowledgeAgent(store, llm)
    direct = build_graph(store, llm)
    assert graph_topology(agent.graph) == graph_topology(direct)
