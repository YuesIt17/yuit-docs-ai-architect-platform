"""Named domain spans for GraphRAG chat path (OBS-01)."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

_TRACER_NAME = "kp.domain"


def get_tracer():
    try:
        from opentelemetry import trace

        return trace.get_tracer(_TRACER_NAME)
    except Exception:
        return None


@contextmanager
def span(name: str, **attrs) -> Iterator[None]:
    """Start a domain span; no-op if OTel is not configured."""
    tracer = get_tracer()
    if tracer is None:
        yield
        return
    with tracer.start_as_current_span(name) as sp:
        for k, v in attrs.items():
            if v is None:
                continue
            try:
                sp.set_attribute(k, v)
            except Exception:
                pass
        yield


def current_trace_id() -> str | None:
    try:
        from opentelemetry import trace

        ctx = trace.get_current_span().get_span_context()
        if not ctx or not ctx.is_valid:
            return None
        return format(ctx.trace_id, "032x")
    except Exception:
        return None
