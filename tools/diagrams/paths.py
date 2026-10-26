"""Shared paths for the diagrams toolchain."""

from __future__ import annotations

from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TOOLS_DIR.parents[1]
ARCH = REPO_ROOT / "architecture"
# Everything diagram-related lives under architecture/diagrams/
GENERATED = ARCH / "diagrams"
MODEL = GENERATED / "model"
GEN_SOURCES = GENERATED / "sources"
SRC_GEN = GEN_SOURCES / "gen"
SRC_MANUAL = GEN_SOURCES / "manual"
GEN_IMAGES = GENERATED / "images"
INVENTORY = GENERATED / "inventory.json"
PROVENANCE = GENERATED / "provenance.json"
SOURCE_MAP = MODEL / "source-map.yaml"
HELM_CHART = REPO_ROOT / "app" / "infra" / "helm" / "knowledge-platform"
COMPOSE_FILE = REPO_ROOT / "app" / "infra" / "docker-compose.yml"
BACKEND = REPO_ROOT / "app" / "backend"
MERMAID_CONFIG = TOOLS_DIR / "mermaid-config.json"
