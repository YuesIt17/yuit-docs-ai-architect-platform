"""Runtime settings (env / .env) for the Knowledge Platform API."""

from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Asymmetric only: an HMAC entry would let the public JWKS key act as a shared secret.
_ALLOWED_OIDC_ALGORITHMS = frozenset({"RS256", "RS384", "RS512", "PS256", "ES256", "ES384", "EdDSA"})


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    log_level: str = "INFO"
    # Demo Bearer role tokens (not production IdP). Set false to deny protected ops without real auth.
    demo_auth_enabled: bool = True
    # OIDC: setting the issuer turns on JWT validation and requires DEMO_AUTH_ENABLED=false.
    oidc_issuer: str = ""
    oidc_audience: str = "kp-api"
    oidc_algorithms: str = "RS256"
    # Where to fetch keys from when the issuer's public URL is not reachable inside the cluster.
    oidc_jwks_url: str = ""
    jwt_secret: str = "dev-retailpartnerx-change-me"
    index_version: str = "v1"
    policy_version: str = "v1"
    prompt_version: str = "v1"

    # Ollama/vLLM URL/model: Helm `llm.baseUrl` / `llm.model` → env, or .env (see .env.example).
    llm_provider: str = "MOCK"  # MOCK | OLLAMA | VLLM
    openai_base_url: str = ""
    openai_api_key: str = "not-needed"
    llm_model: str = "mock-graph-rag"
    # Comma-separated host:port allowlist for runtime LLM URL changes (empty = settings URL only).
    llm_allowed_base_urls: str = (
        "http://127.0.0.1:11434/v1,"
        "http://localhost:11434/v1,"
        "http://host.docker.internal:11434/v1,"
        "http://127.0.0.1:8000/v1,"
        "http://localhost:8000/v1,"
        "http://vllm:8000/v1,"
        "http://host.docker.internal:8000/v1"
    )
    # When false (submission profile), PUT /v1/llm/config cannot set an arbitrary base_url.
    llm_allow_runtime_url_override: bool = False

    # Off by default until cache hits re-authorize sources (SEC-01).
    enable_semantic_cache: bool = False
    # Calibrate per embedding model with evals/calibrate_cache.py.
    semantic_cache_threshold: float = 0.92
    enable_vlm: bool = False
    enable_vision_ocr: bool = True
    # MOCK (pipeline contract, no reading) | RAPIDOCR (local, needs the `ocr` extra).
    ocr_provider: str = "MOCK"

    # memory = in-process store + cache; live = Neo4j/Qdrant/Redis/MinIO on request path
    store_backend: str = "memory"
    # When true with STORE_BACKEND=live, refuse silent memory fallback on retrieve.
    store_strict_live: bool = True
    # GraphRAG resolve step (graph-on). Set false for vector-only A/B.
    enable_graph_resolve: bool = True
    # Optional bounded retrieve→evaluate→refine loop (max iterations).
    retrieval_refine_max: int = 1

    # memory | postgres. Empty: postgres when STORE_BACKEND=live, otherwise memory.
    session_backend: str = ""
    session_pool_size: int = 5
    # Under Vault dynamic credentials: a mounted file read on each new connection, and a
    # connection lifetime shorter than the lease.
    postgres_dsn_file: str = ""
    session_pool_max_lifetime: float = 1800.0

    # inline (in-process, dev and CI) | celery (live stack, needs a worker).
    job_backend: str = "inline"

    # Helm injects these. Postgres holds dialog checkpoints.
    postgres_dsn: str = "postgresql+asyncpg://kp:kp@localhost:5432/knowledge"
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "retailpartnerx"
    qdrant_url: str = "http://localhost:6333"
    redis_url: str = "redis://localhost:6379/0"
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "knowledge-platform"
    minio_secure: bool = False

    otel_exporter_otlp_endpoint: str = "http://localhost:4318"
    otel_service_name: str = "kp-api"
    prometheus_enabled: bool = True

    embedding_provider: str = "MOCK"
    embedding_model: str = "intfloat/multilingual-e5-small"
    embedding_dim: int = 384
    embedding_local_path: str = ""  # air-gap: local weights dir; empty = HF id / hub cache

    datasets_dir: str = "../datasets"

    @property
    def oidc_algorithm_list(self) -> list[str]:
        return [a.strip() for a in self.oidc_algorithms.split(",") if a.strip()]

    @model_validator(mode="after")
    def _auth_modes_cannot_mix(self) -> "Settings":
        if not self.oidc_issuer:
            return self
        if self.demo_auth_enabled:
            raise ValueError("OIDC_ISSUER requires DEMO_AUTH_ENABLED=false: the two auth modes cannot be mixed")
        if not self.oidc_audience:
            raise ValueError("OIDC_ISSUER requires OIDC_AUDIENCE")
        algorithms = self.oidc_algorithm_list
        if not algorithms or not set(algorithms) <= _ALLOWED_OIDC_ALGORITHMS:
            raise ValueError(f"OIDC_ALGORITHMS must be a subset of {sorted(_ALLOWED_OIDC_ALGORITHMS)}")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
