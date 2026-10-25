"""JSON log formatter with optional OpenTelemetry trace_id for Loki ↔ Tempo."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any


class JsonFormatter(logging.Formatter):
    """Emit one JSON object per line: service, level, msg, trace_id (when present)."""

    def __init__(self, service_name: str = "kp-api") -> None:
        super().__init__()
        self.service_name = service_name

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "service": self.service_name,
            "level": record.levelname.lower(),
            "logger": record.name,
            "msg": record.getMessage(),
        }
        trace_id = _current_trace_id()
        if trace_id:
            payload["trace_id"] = trace_id
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def _current_trace_id() -> str | None:
    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        ctx = span.get_span_context() if span else None
        if ctx and ctx.is_valid and ctx.trace_id:
            return format(ctx.trace_id, "032x")
    except Exception:
        return None
    return None


def setup_json_logging(level: int, service_name: str = "kp-api") -> None:
    """Replace root handlers with a single JSON StreamHandler."""
    root = logging.getLogger()
    root.handlers.clear()
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter(service_name=service_name))
    root.addHandler(handler)
    root.setLevel(level)
