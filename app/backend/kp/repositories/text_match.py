"""Lexical matching shared by the retrieval reranker and the agent's refine step."""

from __future__ import annotations

import re

STOP_WORDS = frozenset(
    {
        "about",
        "all",
        "and",
        "are",
        "can",
        "does",
        "for",
        "have",
        "how",
        "know",
        "say",
        "says",
        "tell",
        "that",
        "the",
        "this",
        "what",
        "which",
        "who",
        "why",
        "with",
        "you",
    }
)


def tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"\w+", text.lower()) if len(t) > 2 and t not in STOP_WORDS}


def lexical_hits(query: str, text: str) -> int:
    """Count the distinct meaningful query terms that also appear in text."""
    query_tokens = tokens(query)
    if not query_tokens:
        return 0
    return len(query_tokens & tokens(text))
