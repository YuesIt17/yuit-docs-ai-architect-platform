"""Dialog persistence: a LangGraph checkpointer backed by PostgreSQL."""

from __future__ import annotations

import logging

from kp.config import Settings

logger = logging.getLogger("kp.session_memory")


def uses_postgres(settings: Settings) -> bool:
    backend = settings.session_backend or ("postgres" if settings.store_backend == "live" else "memory")
    return backend == "postgres"


def psycopg_dsn(dsn: str) -> str:
    """POSTGRES_DSN is in SQLAlchemy form, which psycopg does not accept."""
    return dsn.replace("postgresql+asyncpg://", "postgresql://", 1)


async def open_postgres_checkpointer(settings: Settings):
    """Return (saver, pool) with the checkpoint tables created. The caller closes the pool."""
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    from psycopg.rows import dict_row
    from psycopg_pool import AsyncConnectionPool

    pool = AsyncConnectionPool(
        psycopg_dsn(settings.postgres_dsn),
        max_size=settings.session_pool_size,
        open=False,
        kwargs={"autocommit": True, "row_factory": dict_row, "prepare_threshold": 0},
    )
    await pool.open(wait=True, timeout=30)
    saver = AsyncPostgresSaver(pool)
    await saver.setup()
    logger.info("PostgreSQL session memory ready")
    return saver, pool
