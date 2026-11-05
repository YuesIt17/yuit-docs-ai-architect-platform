from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

MAX_STORED_TURNS = 20


def append_turns(existing: list[dict[str, Any]] | None, new: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Keep a bounded dialog so checkpoints do not grow without limit."""
    return ((existing or []) + (new or []))[-MAX_STORED_TURNS:]


class AgentState(TypedDict, total=False):
    request_id: str
    message: str
    modality: str  # chat | label
    role: str
    user_id: str
    route: str
    guarded_message: str
    guard_ok: bool
    guard_reasons: list[str]
    retrieved: list[dict[str, Any]]
    graph_doc_ids: list[str]
    refine_count: int
    label_extract: dict[str, Any]
    answer: str
    citations: list[dict[str, Any]]
    degraded: bool
    acl_decision: str
    tokens_in: int
    tokens_out: int
    model_uri: str
    errors: Annotated[list[str], operator.add]
    # Dialog memory. Only history outlives a turn; see TURN_RESET in graph.py.
    history: Annotated[list[dict[str, Any]], append_turns]
    visible_history: list[dict[str, Any]]
    retrieval_query: str
    session_bound: bool
