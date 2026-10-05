FROM python:3.12-slim

WORKDIR /app
# Prefer wheels-only install to avoid apt (flaky networks / air-gapped builds).
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

COPY backend/pyproject.toml /tmp/pyproject.toml
RUN pip install --no-cache-dir \
    fastapi "uvicorn[standard]" pydantic pydantic-settings python-multipart httpx \
    langgraph langchain-core langchain-openai neo4j qdrant-client redis minio \
    "sqlalchemy[asyncio]" asyncpg prometheus-client \
    opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp \
    opentelemetry-instrumentation-fastapi "python-jose[cryptography]" \
    pillow pypdfium2 numpy pyyaml pytest pytest-asyncio

COPY backend/app ./app
COPY backend/pipelines ./pipelines
COPY backend/scripts ./scripts
COPY datasets /datasets

ENV DATASETS_DIR=/datasets
EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
