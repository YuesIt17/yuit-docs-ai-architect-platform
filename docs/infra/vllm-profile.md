# vLLM submission profile

Desktop convenience remains **Ollama** (`make llm-ollama`, profile `llm`).
Submission / course serving profile is **vLLM** (OpenAI-compatible).

## Chosen stack

| Parameter | Value |
|-----------|--------|
| Image | `vllm/vllm-openai:v0.6.6` |
| Model | `Qwen/Qwen2.5-1.5B-Instruct-AWQ` |
| Quantization | **AWQ** |
| Context length | 4096 |
| Max concurrent seqs | 2 |
| API | `http://localhost:8000/v1` |
| Client | `LLM_PROVIDER=VLLM` |

Alternative for &lt;6 GB VRAM: `Qwen/Qwen2.5-0.5B-Instruct` FP16 — document in model-card if used.

## Start (GPU host)

```bash
# Pre-pull image + weights while online (air-gap prep)
docker compose -f app/infra/docker-compose.yml --profile vllm pull
docker compose -f app/infra/docker-compose.yml --profile vllm up -d
curl -s http://localhost:8000/v1/models
```

Helm overlay:

```bash
helm upgrade --install kp ./app/infra/helm/knowledge-platform \
  -f app/infra/helm/knowledge-platform/values.yaml \
  -f app/infra/helm/knowledge-platform/values-submission-vllm.yaml
```

## GPU unavailable

Static configs and Helm values can be reviewed without a GPU.
**Status: runtime not verified** until `curl /v1/models` succeeds on a machine with NVIDIA GPU + drivers.

## Benchmark

[`scripts/bench_vllm.py`](../../app/backend/scripts/bench_vllm.py) measures time to first token, p95 latency and token throughput at each parallelism level, and writes `docs/evidence/load/bench_<label>.json`. Run it on the GPU host from `app/backend`:

```bash
python scripts/bench_vllm.py --model Qwen/Qwen2.5-1.5B-Instruct-AWQ --concurrency 1 2 4 --label awq-seqs2
```

To size the KV cache for a VRAM limit:

1. Start vLLM with `--gpu-memory-utilization 0.6`. Watch `nvidia-smi` and the `vllm:gpu_cache_usage_perc` metric during a run.
2. Raise `--max-num-seqs` and repeat. Throughput rises until requests queue or preempt, which shows as rising TTFT and `vllm:num_preemptions_total`.
3. Choose the highest setting where p95 TTFT still meets the target, and leave at least 10% of VRAM free for the driver.
4. Record the chosen values in this file and in [capacity-planning.md](../capacity-planning.md).

**No GPU results are recorded yet.** The script is tested against a scripted streaming server, which checks its measurements but not vLLM itself.

Do **not** rename Ollama to vLLM. Do **not** claim GGUF Ollama weights are interchangeable with AWQ vLLM.

## Offline prep

1. Pull `vllm/vllm-openai:v0.6.6` and HF weights for the AWQ model.
2. Pull embedding weights for `intfloat/multilingual-e5-small` into `EMBEDDING_LOCAL_PATH`.
3. Disconnect network and run health/probe checks.

## Vault

HashiCorp Vault remains **planned** (`app/infra/vault/README.md`). Current secrets use Kubernetes `Secret` references (`kp-secrets`), not a live Vault agent.
