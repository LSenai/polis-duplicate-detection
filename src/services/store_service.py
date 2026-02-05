"""
Store flow: embed txt, upsert row (zid, tid, txt, embedding).
Per constitution: conversation-scoped; idempotent for same (zid, tid).
"""

import logging

import asyncpg

from src.api.schemas import StoreResponse
from src.services.embedding import generate_embedding
from src.services.storage import upsert_embedding

logger = logging.getLogger(__name__)


async def store(
    zid: int,
    tid: int,
    txt: str,
    pool: asyncpg.Pool | None,
) -> StoreResponse:
    """
    Store embedding for comment (zid, tid, txt). Idempotent for same (zid, tid).
    Returns StoreResponse(success=True) on success; success=False when DB unavailable or error.
    """
    if pool is None:
        return StoreResponse(success=False)
    embedding = generate_embedding(txt)
    async with pool.acquire() as conn:
        ok = await upsert_embedding(conn, zid, tid, txt, embedding)
    return StoreResponse(success=ok)
