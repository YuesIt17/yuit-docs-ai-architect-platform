from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict


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
    label_extract: dict[str, Any]
    answer: str
    citations: list[dict[str, Any]]
    degraded: bool
    acl_decision: str
    tokens_in: int
    tokens_out: int
    model_uri: str
    errors: Annotated[list[str], operator.add]
