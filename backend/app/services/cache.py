"""Semantic cache stub (hw-9)."""

from __future__ import annotations

from dataclasses import dataclass

from app.config import Settings
from app.services.embeddings import EmbeddingService


@dataclass
class CacheEntry:
    answer: str
    citations: list[dict]
    index_version: str


class SemanticCache:
    def __init__(self, settings: Settings, embeddings: EmbeddingService):
        self.settings = settings
        self.embeddings = embeddings
        self._entries: list[tuple[list[float], str, CacheEntry]] = []
        self.hits = 0
        self.misses = 0
        self.threshold = 0.92

    def get(self, query: str, role: str, index_version: str) -> CacheEntry | None:
        if not self.settings.enable_semantic_cache:
            self.misses += 1
            return None
        q = self.embeddings.embed(f"{role}::{query}")
        best: tuple[float, CacheEntry] | None = None
        for vec, r, entry in self._entries:
            if r != role or entry.index_version != index_version:
                continue
            score = EmbeddingService.cosine(q, vec)
            if best is None or score > best[0]:
                best = (score, entry)
        if best and best[0] >= self.threshold:
            self.hits += 1
            return best[1]
        self.misses += 1
        return None

    def put(self, query: str, role: str, entry: CacheEntry) -> None:
        if not self.settings.enable_semantic_cache:
            return
        vec = self.embeddings.embed(f"{role}::{query}")
        self._entries.append((vec, role, entry))

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return (self.hits / total) if total else 0.0
