# Dependencies come from uv.lock, so the image gets exactly the versions CI tests.
FROM python:3.12-slim AS deps
COPY --from=ghcr.io/astral-sh/uv:0.13.7 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/venv
WORKDIR /build
COPY app/backend/pyproject.toml app/backend/uv.lock ./
# Runtime extras only: the Celery worker and local OCR. Dev, eval and embeddings stay out.
RUN uv sync --frozen --no-dev --no-install-project --no-cache --extra queue --extra ocr

FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PATH=/opt/venv/bin:$PATH
COPY --from=deps /opt/venv /opt/venv

COPY app/backend/kp ./kp
COPY app/backend/pipelines ./pipelines
COPY app/backend/scripts ./scripts
COPY app/datasets /datasets

ENV DATASETS_DIR=/datasets

# A numeric user lets Kubernetes verify runAsNonRoot.
USER 10001
EXPOSE 8080
CMD ["uvicorn", "kp.main:app", "--host", "0.0.0.0", "--port", "8080"]
