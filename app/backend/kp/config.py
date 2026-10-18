"""Runtime settings (env / .env) for the Knowledge Platform API."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    log_level: str = "INFO"
    # Reserved: real JWT verification not wired yet (demo uses Bearer role tokens).
    jwt_secret: str = "dev-retailpartnerx-change-me"
    index_version: str = "v1"
    policy_version: str = "v1"

    # Ollama URL/model: Helm `llm.baseUrl` / `llm.model` → env, or .env (see .env.example).
    llm_provider: str = "MOCK"  # MOCK | OLLAMA
    openai_base_url: str = ""
    openai_api_key: str = "not-needed"
    llm_model: str = "mock-graph-rag"

    enable_semantic_cache: bool = True
    enable_vlm: bool = False
    enable_vision_ocr: bool = True

    # memory = in-process store + cache; live = Neo4j/Qdrant/Redis/MinIO on request path
    store_backend: str = "memory"

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
    embedding_model: str = "intfloat/multilingual-e5-base"
    embedding_dim: int = 384

    datasets_dir: str = "../datasets"


@lru_cache
def get_settings() -> Settings:
    return Settings()
