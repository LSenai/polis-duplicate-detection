"""
Check flow: embed text, query similar, classify each match, determine overall tier, build CheckResponse.
Per constitution: composable pipeline; no single function that both computes embeddings and classifies policy.
"""

import logging
import asyncpg

from src.api.schemas import CheckResponse, SimilarComment
from src.config.settings import THRESHOLD_BLOCK, THRESHOLD_RELATED, THRESHOLD_WARN
from src.services.embedding import generate_embedding
from src.services.storage import query_similar
from src.services.similarity import classify_tier

logger = logging.getLogger(__name__)


def _tier_rank(tier: str) -> int:
    """Return numeric rank for overall tier: block (3) > warn (2) > related (1) > allow (0)."""
    return {"block": 3, "warn": 2, "related": 1, "allow": 0}[tier]


async def check(
    zid: int,
    txt: str,
    pool: asyncpg.Pool | None,
) -> CheckResponse:
    """
    Check comment for semantic duplicates in conversation zid.
    Returns tier and similar_comments; overall tier is the highest among matches (block > warn > related).
    """
    embedding = generate_embedding(txt)
    if pool is None:
        return CheckResponse(tier="allow", similar_comments=[])
    async with pool.acquire() as conn:
        rows = await query_similar(conn, zid, embedding)

    similar_comments: list[SimilarComment] = []
    overall_rank = 0
    for tid, text, score in rows:
        tier = classify_tier(
            score,
            threshold_block=THRESHOLD_BLOCK,
            threshold_warn=THRESHOLD_WARN,
            threshold_related=THRESHOLD_RELATED,
        )
        if tier != "allow":
            similar_comments.append(
                SimilarComment(tid=tid, txt=text, similarity=round(score, 4), tier=tier)
            )
            overall_rank = max(overall_rank, _tier_rank(tier))

    overall_tier = "allow"
    if overall_rank >= 3:
        overall_tier = "block"
    elif overall_rank >= 2:
        overall_tier = "warn"
    elif overall_rank >= 1:
        overall_tier = "related"

    return CheckResponse(tier=overall_tier, similar_comments=similar_comments)
