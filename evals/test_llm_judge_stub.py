"""LLM-as-Judge stub for prompt regression (no external API)."""

from __future__ import annotations

GOLD = [
    {
        "question": "Какие аллергены у FreshFarm oats?",
        "must_include": ["gluten", "nuts"],
        "must_not_include": ["42%"],
    },
    {
        "question": "Q4 Closed Promo Margin",
        "role": "category_manager",
        "must_not_include": ["42%", "transfer price"],
    },
]


def judge(answer: str, case: dict) -> tuple[bool, str]:
    low = answer.lower()
    for needle in case.get("must_include") or []:
        if needle.lower() not in low:
            return False, f"missing:{needle}"
    for needle in case.get("must_not_include") or []:
        if needle.lower() in low:
            return False, f"leaked:{needle}"
    return True, "ok"


def test_gold_cases_structure():
    assert len(GOLD) >= 2
    ok, reason = judge("FreshFarm contains gluten and nuts", GOLD[0])
    assert ok, reason
