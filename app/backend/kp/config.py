"""Runtime settings (env / .env) for the Knowledge Platform API."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    log_level: str = "INFO"
    # Demo Bearer role tokens (not production IdP). Set false to deny protected ops without real auth.
    demo_auth_enabled: bool = True
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
    enable_vlm: bool = False
    enable_vision_ocr: bool = True

    # memory = in-process store + cache; live = Neo4j/Qdrant/Redis/MinIO on request path
    store_backend: str = "memory"
    # When true with STORE_BACKEND=live, refuse silent memory fallback on retrieve.
    store_strict_live: bool = True
    # GraphRAG resolve step (graph-on). Set false for vector-only A/B.
    enable_graph_resolve: bool = True
    # Optional bounded retrieve→evaluate→refine loop (max iterations).
    retrieval_refine_max: int = 1

    # Helm still injects these; postgres reserved for a future metadata store.
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


@lru_cache
def get_settings() -> Settings:
    return Settings()
