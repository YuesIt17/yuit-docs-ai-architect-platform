"""FastAPI entrypoint: CORS, routers, OTel, /metrics, startup seed."""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.responses import Response

from kp import __version__
from kp.api.router import router
from kp.config import get_settings
from kp.deps import get_container
from kp.observability.tracing import setup_otel
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

    setup_otel(app, settings)

    @app.on_event("startup")
    async def _startup() -> None:
        c = get_container()
        seed_store(c.store)
        logger.info(
            "KP started store=%s live=%s llm=%s otel=%s docs=%s",
            settings.store_backend,
            getattr(c.store, "live_enabled", False),
            settings.llm_provider,
            settings.otel_exporter_otlp_endpoint,
            c.store.graph_stats(),
        )

    if settings.prometheus_enabled:

        @app.get("/metrics")
        async def metrics() -> Response:
            return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    return app


app = create_app()
