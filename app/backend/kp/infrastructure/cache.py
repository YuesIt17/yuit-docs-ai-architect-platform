"""Semantic answer cache: in-process by default, Redis-backed in live mode."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field

from kp.config import Settings
from kp.infrastructure.embeddings import EmbeddingService

logger = logging.getLogger("kp.cache")


@dataclass
class CacheEntry:
    answer: str
    citations: list[dict]
    index_version: str
    policy_version: str = "v1"
    prompt_version: str = "v1"
    model_uri: str = ""
    source_doc_ids: list[str] = field(default_factory=list)


class InProcessSemanticCache:
    """Process-local cosine cache (CI / memory backend)."""

    def __init__(self, settings: Settings, embeddings: EmbeddingService):
        self.settings = settings
        self.embeddings = embeddings
        self._entries: list[tuple[list[float], str, CacheEntry]] = []
        self.hits = 0
        self.misses = 0
        self.threshold = 0.92

    def get(
        self,
        query: str,
        role: str,
        index_version: str,
        *,
        policy_version: str,
        prompt_version: str,
        model_uri: str,
    ) -> CacheEntry | None:
        if not self.settings.enable_semantic_cache:
            self.misses += 1
            return None
        q = self.embeddings.embed(f"{role}::{query}")
        best: tuple[float, CacheEntry] | None = None
        for vec, r, entry in self._entries:
            if r != role:
                continue
            if entry.index_version != index_version:
                continue
            if entry.policy_version != policy_version:
                continue
            if entry.prompt_version != prompt_version:
                continue
            if entry.model_uri != model_uri:
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


class RedisSemanticCache:
    """Shared semantic cache stored in Redis (cosine match in-process)."""

    KEY = "kp:semantic_cache:v2"

    def __init__(self, settings: Settings, embeddings: EmbeddingService):
        self.settings = settings
        self.embeddings = embeddings
        self.hits = 0
        self.misses = 0
        self.threshold = 0.92
        self._redis = None
        self._fallback = InProcessSemanticCache(settings, embeddings)
        try:
            import redis

            client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
            client.ping()
            self._redis = client
            logger.info("Redis semantic cache connected (%s)", settings.redis_url)
        except Exception as exc:
            logger.warning("Redis unavailable, using in-process cache: %s", exc)
            self._redis = None

    def _load(self) -> list[tuple[list[float], str, CacheEntry]]:
        if not self._redis:
            return []
        try:
            raw = self._redis.get(self.KEY)
            if not raw:
                return []
            items = json.loads(raw)
            out: list[tuple[list[float], str, CacheEntry]] = []
            for item in items:
                e = item["entry"]
                out.append(
                    (
                        item["vec"],
                        item["role"],
                        CacheEntry(
                            answer=e["answer"],
                            citations=e["citations"],
                            index_version=e["index_version"],
                            policy_version=e.get("policy_version", "v1"),
                            prompt_version=e.get("prompt_version", "v1"),
                            model_uri=e.get("model_uri", ""),
                            source_doc_ids=list(e.get("source_doc_ids") or []),
                        ),
                    )
                )
            return out
        except Exception as exc:
            logger.warning("Redis cache load failed: %s", exc)
            return []

    def _save(self, entries: list[tuple[list[float], str, CacheEntry]]) -> None:
        if not self._redis:
            return
        try:
            payload = [
                {"vec": vec, "role": role, "entry": asdict(entry)} for vec, role, entry in entries[-500:]
            ]
            self._redis.set(self.KEY, json.dumps(payload))
        except Exception as exc:
            logger.warning("Redis cache save failed: %s", exc)

    def get(
        self,
        query: str,
        role: str,
        index_version: str,
        *,
        policy_version: str,
        prompt_version: str,
        model_uri: str,
    ) -> CacheEntry | None:
        if not self.settings.enable_semantic_cache:
            self.misses += 1
            return None
        if not self._redis:
            entry = self._fallback.get(
                query,
                role,
                index_version,
                policy_version=policy_version,
                prompt_version=prompt_version,
                model_uri=model_uri,
            )
            self.hits = self._fallback.hits
            self.misses = self._fallback.misses
            return entry
        q = self.embeddings.embed(f"{role}::{query}")
        best: tuple[float, CacheEntry] | None = None
        try:
            for vec, r, entry in self._load():
                if r != role:
                    continue
                if entry.index_version != index_version:
                    continue
                if entry.policy_version != policy_version:
                    continue
                if entry.prompt_version != prompt_version:
                    continue
                if entry.model_uri != model_uri:
                    continue
                score = EmbeddingService.cosine(q, vec)
                if best is None or score > best[0]:
                    best = (score, entry)
        except Exception as exc:
            logger.warning("Redis cache get failed: %s", exc)
            self.misses += 1
            return None
        if best and best[0] >= self.threshold:
            self.hits += 1
            return best[1]
        self.misses += 1
        return None

    def put(self, query: str, role: str, entry: CacheEntry) -> None:
        if not self.settings.enable_semantic_cache:
            return
        if not self._redis:
            self._fallback.put(query, role, entry)
            return
        try:
            vec = self.embeddings.embed(f"{role}::{query}")
            entries = self._load()
            entries.append((vec, role, entry))
            self._save(entries)
        except Exception as exc:
            logger.warning("Redis cache put failed: %s", exc)

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return (self.hits / total) if total else 0.0


def build_semantic_cache(settings: Settings, embeddings: EmbeddingService):
    """Pick Redis cache for live backend, in-process otherwise."""
    if settings.store_backend == "live":
        return RedisSemanticCache(settings, embeddings)
    return InProcessSemanticCache(settings, embeddings)


SemanticCache = InProcessSemanticCache
