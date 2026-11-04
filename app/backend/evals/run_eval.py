"""Evaluate the golden set; exit 1 if any threshold is breached.

Deterministic gate (CI, no model needed):
  python -m evals.run_eval

With the local LLM judge:
  python -m evals.run_eval --judge --judge-base-url http://127.0.0.1:11434/v1 --judge-model qwen2.5:1.5b
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from evals.harness import check_deterministic, load_golden, run_case, summarize
from kp.deps import get_container
from pipelines.seed_all import seed_store

THRESHOLDS = Path(__file__).with_name("thresholds.json")


async def _run_all(agent, cases) -> list:
    # One at a time: the local model serves few parallel sequences, and CI output stays ordered.
    return [await run_case(agent, case) for case in cases]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--judge", action="store_true", help="also score answers with the local LLM judge")
    parser.add_argument("--judge-base-url", default="http://127.0.0.1:11434/v1")
    parser.add_argument("--judge-model", default="qwen2.5:0.5b")
    parser.add_argument("--report", type=Path, default=None, help="write the JSON report to this path")
    args = parser.parse_args(argv)

    container = get_container()
    seed_store(container.store)
    limits = json.loads(THRESHOLDS.read_text(encoding="utf-8"))
    results = asyncio.run(_run_all(container.agent, load_golden()))

    summary = summarize(results)
    failures = check_deterministic(summary, limits["deterministic"])
    report = {
        "llm": container.llm.get_config().model_uri,
        "embeddings": container.settings.embedding_provider,
        "summary": summary,
        "cases": [
            {
                "id": r.case.id,
                "role": r.case.role,
                "recall": r.recall,
                "refused": r.refused,
                "cited": r.cited_doc_ids,
                "leaks": r.leaks,
                "acl_decision": r.acl_decision,
            }
            for r in results
        ],
    }

    if args.judge:
        from evals.judge import build_judge, check_judge, score_results

        judged = score_results(results, build_judge(args.judge_base_url, args.judge_model))
        report["judge"] = judged
        failures += check_judge(judged["means"], limits["judge"])

    report["failures"] = failures
    text = json.dumps(report, ensure_ascii=False, indent=2)
    print(text)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(text + "\n", encoding="utf-8")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
