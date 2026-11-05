FROM python:3.12-slim

WORKDIR /app
# Prefer wheels-only install to avoid apt (flaky networks / air-gapped builds).
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

COPY app/backend/pyproject.toml /tmp/pyproject.toml
RUN pip install --no-cache-dir \
    fastapi "uvicorn[standard]" pydantic pydantic-settings python-multipart httpx \
    langgraph langchain-core langchain-openai neo4j qdrant-client redis minio \
    prometheus-client \
    opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp \
    opentelemetry-instrumentation-fastapi \
    pillow pypdfium2 "pyjwt[crypto]>=2.10,<3" \
    "langgraph-checkpoint-postgres>=3.2,<4" "psycopg[binary,pool]>=3.2" "celery[redis]>=5.5,<6"

# OCR without apt: rapidocr pulls opencv-python, which needs libGL, so the headless build replaces it.
RUN pip install --no-cache-dir opencv-python-headless onnxruntime pyclipper shapely pyyaml six tqdm numpy \
    && pip install --no-cache-dir --no-deps "rapidocr-onnxruntime>=1.2,<2"

COPY app/backend/kp ./kp
COPY app/backend/pipelines ./pipelines
COPY app/backend/scripts ./scripts
COPY app/datasets /datasets

ENV DATASETS_DIR=/datasets

# A numeric user lets Kubernetes verify runAsNonRoot.
USER 10001
EXPOSE 8080
CMD ["uvicorn", "kp.main:app", "--host", "0.0.0.0", "--port", "8080"]
