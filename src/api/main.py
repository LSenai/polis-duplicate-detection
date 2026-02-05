"""
FastAPI application: structured logging, error handlers, health and check routes.
Per constitution: structured logging; consistent error structure; health endpoint.
"""

import logging
import sys
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI

from src.api.errors import register_error_handlers
from src.api.routes import router as api_router
from src.services.db import get_pool

# Structured logging: key-value style for machine parsing.
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s %(name)s %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Create DB pool on startup; close on shutdown."""
    pool = None
    try:
        pool = await get_pool()
    except Exception as e:
        logger.warning("DB pool not available: %s", e)
    app.state.pool = pool
    yield
    if pool is not None:
        await pool.close()


def create_app() -> FastAPI:
    """Create and configure the FastAPI app."""
    app = FastAPI(
        title="Duplicate Detection API",
        description="Semantic duplicate/paraphrase detection for Polis comments.",
        version="0.1.0",
        lifespan=lifespan,
    )
    register_error_handlers(app)
    app.include_router(api_router, tags=["health", "duplicate-check"])
    logger.info("Application configured")
    return app


app = create_app()
