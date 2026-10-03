"""Embedding providers: MOCK (deterministic) for CI, optional live later."""

from __future__ import annotations

import hashlib
import math
import re

from app.config import Settings


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[\wа-яё]+", text.lower(), flags=re.IGNORECASE)


class EmbeddingService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.dim = settings.embedding_dim

    def embed(self, text: str) -> list[float]:
        if self.settings.embedding_provider.upper() != "MOCK":
            # Fallback to mock until sentence-transformers wired in vision profile
            return self._mock_embed(text)
        return self._mock_embed(text)

    def _mock_embed(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        tokens = _tokenize(text) or ["empty"]
        for tok in tokens:
            digest = hashlib.sha256(tok.encode("utf-8")).digest()
            for i in range(0, min(len(digest), 32)):
                idx = (digest[i] * (i + 1) + len(tok)) % self.dim
                vec[idx] += (digest[i] / 255.0) * 2 - 1
        # L2 normalize
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    @staticmethod
    def cosine(a: list[float], b: list[float]) -> float:
        return sum(x * y for x, y in zip(a, b, strict=False))
