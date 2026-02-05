"""
Storage layer: query similar comments by zid and embedding (pgvector cosine similarity).
Per constitution: conversation-scoped; no cross-conversation; indexed search.
"""

import logging
from typing import Any

import asyncpg

logger = logging.getLogger(__name__)

# Minimum similarity to return (e.g. related threshold); fetch candidates for tiering.
MIN_SIMILARITY_QUERY = 0.75
LIMIT_SIMILAR = 10


async def query_similar(
    conn: asyncpg.Connection | None,
    zid: int,
    embedding: list[float],
    *,
    limit: int = LIMIT_SIMILAR,
    min_similarity: float = MIN_SIMILARITY_QUERY,
) -> list[tuple[int, str, float]]:
    """
    Return list of (tid, txt, similarity) for comments in conversation zid
    with cosine similarity above min_similarity, ordered by similarity desc.
    Returns [] if conn is None (no DB) or on error.
    """
    if conn is None:
        return []
    try:
        # pgvector: cosine distance is <=>; similarity = 1 - distance.
        # Embedding as string for asyncpg if vector type not registered.
        emb_str = "[" + ",".join(str(x) for x in embedding) + "]"
        rows = await conn.fetch(
            """
            SELECT tid, txt, 1 - (embedding <=> $1::vector) AS similarity
            FROM comment_embeddings
            WHERE zid = $2 AND (1 - (embedding <=> $1::vector)) > $3
            ORDER BY embedding <=> $1::vector
            LIMIT $4
            """,
            emb_str,
            zid,
            min_similarity,
            limit,
        )
        return [(r["tid"], r["txt"], float(r["similarity"])) for r in rows]
    except Exception as e:
        logger.exception("query_similar failed: %s", e)
        return []


async def upsert_embedding(
    conn: asyncpg.Connection | None,
    zid: int,
    tid: int,
    txt: str,
    embedding: list[float],
) -> bool:
    """
    Upsert one row (zid, tid, txt, embedding). Idempotent for same (zid, tid).
    Returns True on success, False if conn is None or on error.
    """
    if conn is None:
        return False
    try:
        emb_str = "[" + ",".join(str(x) for x in embedding) + "]"
        await conn.execute(
            """
            INSERT INTO comment_embeddings (zid, tid, txt, embedding)
            VALUES ($1, $2, $3, $4::vector)
            ON CONFLICT (zid, tid) DO UPDATE SET
                txt = EXCLUDED.txt,
                embedding = EXCLUDED.embedding
            """,
            zid,
            tid,
            txt,
            emb_str,
        )
        return True
    except Exception as e:
        logger.exception("upsert_embedding failed: %s", e)
        return False
