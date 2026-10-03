FROM python:3.12-slim

WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl && rm -rf /var/lib/apt/lists/*

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

ENV PYTHONPATH=/app
ENV DATASETS_DIR=/datasets
EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]