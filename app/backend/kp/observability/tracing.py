"""OpenTelemetry / Jaeger wiring for FastAPI."""

from __future__ import annotations

import logging

from fastapi import FastAPI

logger = logging.getLogger("kp")


def setup_otel(app: FastAPI, settings) -> None:
    """Wire OTLP/HTTP traces → Jaeger (Compose :4318/v1/traces). Failures are non-fatal."""
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        endpoint = (settings.otel_exporter_otlp_endpoint or "").strip().rstrip("/")
        if not endpoint:
            logger.warning("OTel skipped: empty OTEL_EXPORTER_OTLP_ENDPOINT")
            return
        if endpoint.endswith(":4317"):
            endpoint = endpoint[:-5] + ":4318"
        if not endpoint.endswith("/v1/traces"):
            endpoint = f"{endpoint}/v1/traces"

        resource = Resource.create({"service.name": settings.otel_service_name})
        provider = TracerProvider(resource=resource)
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
        trace.set_tracer_provider(provider)
        FastAPIInstrumentor.instrument_app(app, excluded_urls="metrics,health")
        logger.info("OTel enabled → %s (service=%s)", endpoint, settings.otel_service_name)
    except Exception as exc:
        logger.warning("OTel not fully enabled: %s", exc)
