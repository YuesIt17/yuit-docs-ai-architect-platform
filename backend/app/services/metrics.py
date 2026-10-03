from prometheus_client import Counter, Histogram, Gauge

LLM_TOKENS = Counter("llm_tokens_total", "LLM tokens", ["direction"])
RAG_LATENCY = Histogram("rag_latency_ms", "RAG pipeline latency ms")
VISION_LATENCY = Histogram("vision_latency_ms", "Vision pipeline latency ms")
CACHE_HIT_RATE = Gauge("semantic_cache_hit_rate", "Semantic cache hit rate")
REQUESTS = Counter("kp_requests_total", "API requests", ["endpoint", "status"])
ACL_DENIES = Counter("acl_denies_total", "ACL denials", ["role"])
