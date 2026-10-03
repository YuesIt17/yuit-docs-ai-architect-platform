from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.responses import Response

from app import __version__
from app.api.routes import router
from app.config import get_settings
from app.deps import get_container
from pipelines.seed_all import seed_store

logger = logging.getLogger("kp")


def create_app() -> FastAPI:
    settings = get_settings()
    logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))

    app = FastAPI(
        title="RetailPartnerX Knowledge Platform",
        description="GraphRAG + multimodal label recognition — Google PE style Control/Data Plane",
        version=__version__,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)

    @app.on_event("startup")
    async def _startup() -> None:
        c = get_container()
        seed_store(c.store)
        _setup_otel(settings)
        logger.info(
            "KP started store=%s llm=%s docs=%s",
            settings.store_backend,
            settings.llm_provider,
            c.store.graph_stats(),
        )

    @app.get("/metrics")
    async def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    return app


def _setup_otel(settings) -> None:
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        resource = Resource.create({"service.name": settings.otel_service_name})
        provider = TracerProvider(resource=resource)
        exporter = OTLPSpanExporter(endpoint=settings.otel_exporter_otlp_endpoint, insecure=True)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
        # Instrumentation attached lazily on app instance in create_app if needed
        FastAPIInstrumentor().instrument()
    except Exception as exc:
        logging.getLogger("kp").warning("OTel not fully enabled: %s", exc)


app = create_app()
