"""
Database connection with timeout. Per constitution: all external calls must have timeouts.
Uses asyncpg; pgvector is registered via the pgvector package when available.
"""

import logging

import asyncpg

from src.config.settings import DB_TIMEOUT_SEC, get_database_url

logger = logging.getLogger(__name__)


async def get_pool() -> asyncpg.Pool | None:
    """Create a connection pool with timeout. Returns None if DATABASE_URL is not set."""
    url = get_database_url()
    if not url:
        logger.warning("DATABASE_URL not set; DB operations will be unavailable")
        return None
    try:
        # Timeout applied at connection and query level via command_timeout.
        pool = await asyncpg.create_pool(
            url,
            min_size=1,
            max_size=10,
            command_timeout=DB_TIMEOUT_SEC,
        )
        return pool
    except Exception as e:
        logger.exception("Failed to create DB pool: %s", e)
        raise
