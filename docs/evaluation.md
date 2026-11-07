# RAG Evaluation

Answer quality is checked at two levels. The commands below run from `app/backend`.

| Level | What it checks | Needs a model | Runs in |
| ----- | -------------- | ------------- | ------- |
| Deterministic gate | Retrieval recall, ACL leaks, refusals | No | CI, on every change |
| LLM judge (DeepEval) | Faithfulness, answer relevancy, contextual precision and recall | Yes, local only | Before changing prompts or model weights |

The judge does not replace the ACL tests: a metric score can never prove that a secret did not leak.

## Deterministic gate

```bash
python -m evals.run_eval --report ../../tmp/evals/report.json
```

The command runs [`evals/golden.jsonl`](../app/backend/evals/golden.jsonl) through the real agent and exits with code 1 if it breaches a limit in [`evals/thresholds.json`](../app/backend/evals/thresholds.json).

A forbidden document counts as a leak if it is cited **or** reaches the LLM as context.

Current result on MOCK LLM and MOCK embeddings, 12 cases:

| Metric | Value | Gate |
| ------ | ----- | ---- |
| ACL leaks | 0 | 0 |
| Refusal accuracy | 1.00 | 1.00 |
| Retrieval recall | 1.00 | ≥ 0.90 |
| Citation precision | 0.39 | reported only |

The low citation precision is a real weakness. Answers often cite related documents beyond the one required, because MOCK embeddings and lexical matching rank broadly. Repeat this measurement with LOCAL embeddings before drawing conclusions about production quality.

## LLM judge

```bash
uv sync --extra dev --extra eval
python -m evals.run_eval --judge --judge-base-url http://127.0.0.1:11434/v1 --judge-model qwen2.5:1.5b
```

- **Closed perimeter:** the judge refuses any endpoint outside the local host list, and DeepEval telemetry is turned off.
- **Unscored metrics fail the gate:** if a model returns malformed JSON for every case, the run fails instead of passing with no data. Failures are listed under `judge.errors`.
- **Model choice:** `qwen2.5:0.5b` is too small to judge reliably. Use `1.5b` or larger.

**Status:** the wiring is verified with real DeepEval metrics against a stub endpoint. No scores from a real model have been recorded yet, and the limits in `thresholds.json` are starting values to adjust after the first real run.

DeepEval was chosen over Ragas because Ragas 0.4 does not install on this project's Python 3.14 environment (its `scikit-network` dependency fails to build).

## Semantic cache calibration

```bash
EMBEDDING_PROVIDER=LOCAL python -m evals.calibrate_cache
```

The script sweeps thresholds over the labeled pairs in [`evals/cache_pairs.jsonl`](../app/backend/evals/cache_pairs.jsonl) and recommends one by F0.5, because a false hit serves a wrong answer while a false miss only costs an LLM call. Apply the result with `SEMANTIC_CACHE_THRESHOLD`.

The default stays at `0.92` until it is calibrated with LOCAL embeddings. A MOCK run is marked `"reliable": false`: bag-of-hash similarity says nothing about real embeddings.

## Partial cache invalidation

Each cached answer stores a content hash of every cited document. On a cache hit, a changed hash evicts only the entries that cite that document, and other answers stay cached. This works across API replicas with no invalidation messages, because the check happens on read. `semantic_cache_evictions_total` counts the evictions.
