"""Prometheus counters/histograms scraped via /metrics (Grafana KP Overview)."""

from prometheus_client import Counter, Gauge, Histogram

# Latency is recorded in milliseconds (see application.audit / vision path).
_MS_BUCKETS = (5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000, 30000)

LLM_TOKENS = Counter("llm_tokens_total", "LLM tokens", ["direction"])
RAG_LATENCY = Histogram("rag_latency_ms", "RAG pipeline latency ms", buckets=_MS_BUCKETS)
VISION_LATENCY = Histogram("vision_latency_ms", "Vision pipeline latency ms", buckets=_MS_BUCKETS)
CACHE_HIT_RATE = Gauge("semantic_cache_hit_rate", "Semantic cache hit rate")
REQUESTS = Counter("kp_requests_total", "API requests", ["endpoint", "status"])
ACL_DENIES = Counter("acl_denies_total", "ACL denials", ["role"])
