"""Find the semantic cache threshold from labeled question pairs.

A false hit serves a wrong answer while a false miss only costs an LLM call, so the
threshold is chosen by F0.5, which weights precision over recall.

Results only apply to the embedding model they were measured with. MOCK embeddings
are a bag of hashes, so a MOCK run is marked unreliable:
  EMBEDDING_PROVIDER=LOCAL python -m evals.calibrate_cache
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from kp.config import get_settings
from kp.infrastructure.embeddings import EmbeddingService

PAIRS_PATH = Path(__file__).with_name("cache_pairs.jsonl")
BETA = 0.5


def load_pairs(path: Path = PAIRS_PATH) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def score_threshold(scored: list[tuple[float, bool]], threshold: float) -> dict:
    tp = sum(1 for score, same in scored if score >= threshold and same)
    fp = sum(1 for score, same in scored if score >= threshold and not same)
    fn = sum(1 for score, same in scored if score < threshold and same)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    denominator = BETA**2 * precision + recall
    f_beta = (1 + BETA**2) * precision * recall / denominator if denominator else 0.0
    return {
        "threshold": threshold,
        "precision": precision,
        "recall": recall,
        "f_beta": f_beta,
        "false_hits": fp,
    }


def calibrate(scored: list[tuple[float, bool]]) -> dict:
    """Pick the best threshold; on a tie, the highest one, since it serves fewer wrong answers."""
    grid = [round(0.50 + i * 0.01, 2) for i in range(50)]
    table = [score_threshold(scored, t) for t in grid]
    best = max(table, key=lambda row: (row["f_beta"], row["threshold"]))
    return {"best": best, "table": table}


def main() -> int:
    settings = get_settings()
    embeddings = EmbeddingService(settings)
    role = "store_associate"  # Same "role::question" key the cache embeds.
    scored = [
        (
            EmbeddingService.cosine(
                embeddings.embed(f"{role}::{pair['a']}"),
                embeddings.embed(f"{role}::{pair['b']}"),
            ),
            bool(pair["same"]),
        )
        for pair in load_pairs()
    ]
    result = calibrate(scored)
    print(
        json.dumps(
            {
                "embedding_provider": settings.embedding_provider,
                "reliable": settings.embedding_provider.upper() != "MOCK",
                "current_threshold": settings.semantic_cache_threshold,
                "current": score_threshold(scored, settings.semantic_cache_threshold),
                "recommended": result["best"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
