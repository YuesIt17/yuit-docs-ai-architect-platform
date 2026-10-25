"""Embedding providers: MOCK (CI) | LOCAL (sentence-transformers / e5-small)."""

from __future__ import annotations

import hashlib
import logging
import math
import re
from pathlib import Path

from kp.config import Settings

logger = logging.getLogger("kp.embeddings")


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[\wа-яё]+", text.lower(), flags=re.IGNORECASE)


class EmbeddingService:
    """MOCK = deterministic bag-of-hash; LOCAL = multilingual-e5-small (or configured model)."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.dim = settings.embedding_dim
        self.provider = settings.embedding_provider.upper()
        self._model = None
        if self.provider == "MOCK":
            return
        if self.provider in {"LOCAL", "E5", "SENTENCE_TRANSFORMERS"}:
            self._load_local()
            return
        raise RuntimeError(
            f"Unknown EMBEDDING_PROVIDER={settings.embedding_provider!r}. "
            "Use MOCK (tests) or LOCAL (sentence-transformers). Refusing silent mock fallback."
        )

    def _load_local(self) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError(
                "LOCAL embeddings require optional dependency: pip install '.[embeddings]'"
            ) from exc
        model_id = (self.settings.embedding_local_path or self.settings.embedding_model).strip()
        local = Path(model_id)
        # Air-gap: prefer explicit local path when it exists.
        if local.exists():
            model_id = str(local)
        logger.info("Loading local embedding model %s (expected dim=%s)", model_id, self.dim)
        self._model = SentenceTransformer(model_id)
        # Verify dimension against a probe encode.
        probe = self._model.encode("query: dim check", normalize_embeddings=True)
        actual = int(len(probe))
        if actual != self.dim:
            raise RuntimeError(
                f"Embedding dim mismatch: model={actual} settings.embedding_dim={self.dim}. "
                "Bump INDEX_VERSION and reindex after fixing EMBEDDING_DIM."
            )

    def embed(self, text: str, *, is_query: bool = False) -> list[float]:
        if self.provider == "MOCK":
            return self._mock_embed(text)
        assert self._model is not None
        # E5 family expects "query: " / "passage: " prefixes (official model card).
        model_name = (self.settings.embedding_model or "").lower()
        if "e5" in model_name:
            prefix = "query: " if is_query else "passage: "
            text = prefix + text
        vec = self._model.encode(text, normalize_embeddings=True)
        return [float(x) for x in vec.tolist()]

    def _mock_embed(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        tokens = _tokenize(text) or ["empty"]
        for tok in tokens:
            digest = hashlib.sha256(tok.encode("utf-8")).digest()
            for i in range(0, min(len(digest), 32)):
                idx = (digest[i] * (i + 1) + len(tok)) % self.dim
                vec[idx] += (digest[i] / 255.0) * 2 - 1
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    @staticmethod
    def cosine(a: list[float], b: list[float]) -> float:
        return sum(x * y for x, y in zip(a, b, strict=False))
