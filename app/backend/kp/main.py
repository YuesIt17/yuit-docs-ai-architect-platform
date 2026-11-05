"""FastAPI entrypoint: CORS, routers, OTel, /metrics, startup seed."""

from __future__ import annotations

import asyncio
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.responses import Response

from kp import __version__
from kp.api.router import router
from kp.application.jobs import follow_mirror_stream
from kp.config import get_settings
from kp.deps import get_container
from kp.infrastructure.session_memory import open_postgres_checkpointer, uses_postgres
from kp.observability.logging_json import setup_json_logging
from kp.observability.tracing import setup_otel
from pipelines.seed_all import seed_store

logger = logging.getLogger("kp")


def create_app() -> FastAPI:
    settings = get_settings()
    setup_json_logging(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        service_name=settings.otel_service_name,
    )

    app = FastAPI(
        title="RetailPartnerX Knowledge Platform",
        description="GraphRAG + multimodal label recognition — Google PE style Control/Data Plane",
        version=__version__,
    )
    # Under OIDC the browser only talks to the same-origin BFF, so no cross-origin access is granted.
    if settings.demo_auth_enabled:
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
        if uses_postgres(settings):
            saver, app.state.session_pool = await open_postgres_checkpointer(settings)
            c.agent.attach_checkpointer(saver)
        if settings.job_backend == "celery":
            app.state.mirror_task = asyncio.create_task(follow_mirror_stream(c.store, c.job_redis))
        logger.info(
            "KP started store=%s live=%s llm=%s otel=%s docs=%s",
            settings.store_backend,
            getattr(c.store, "live_enabled", False),
            settings.llm_provider,
            settings.otel_exporter_otlp_endpoint,
            c.store.graph_stats(),
        )

    @app.on_event("shutdown")
    async def _shutdown() -> None:
        mirror = getattr(app.state, "mirror_task", None)
        if mirror is not None:
            mirror.cancel()
        pool = getattr(app.state, "session_pool", None)
        if pool is not None:
            await pool.close()

    if settings.prometheus_enabled:

        @app.get("/metrics")
        async def metrics() -> Response:
            return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    return app


app = create_app()
