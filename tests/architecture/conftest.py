"""Ensure architecture tests can import toolchain and backend."""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
for p in (REPO / "tools" / "diagrams", REPO / "app" / "backend"):
    s = str(p)
    if s not in sys.path:
        sys.path.insert(0, s)
