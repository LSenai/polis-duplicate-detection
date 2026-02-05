"""
API routes: health (readiness), POST /check, POST /store.
Per constitution: small, stable API surface; JSON-only; fail-open on errors.
"""

import logging
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from src.api.errors import error_response
from src.api.schemas import CheckRequest, CheckResponse, StoreRequest, StoreResponse
from src.services.check_service import check
from src.services.store_service import store

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, Any]:
    """
    Health or readiness endpoint for deployment/load balancer.
    Does not perform heavy checks (e.g. no DB ping).
    """
    return {"status": "ok"}


@router.post("/check", response_model=CheckResponse)
async def check_duplicate(request: Request, body: CheckRequest) -> CheckResponse | JSONResponse:
    """
    Check comment for semantic duplicates in conversation zid.
    Returns tier (block/warn/related/allow) and similar_comments.
    Fail-open: on internal error returns tier=allow, similar_comments=[].
    """
    pool = getattr(request.app.state, "pool", None)
    try:
        return await check(body.zid, body.txt, pool)
    except Exception as e:
        logger.exception("check failed, failing open: %s", e)
        return CheckResponse(tier="allow", similar_comments=[])


@router.post("/store", response_model=StoreResponse)
async def store_embedding(request: Request, body: StoreRequest) -> StoreResponse | JSONResponse:
    """
    Store embedding for comment (zid, tid, txt) after comment is accepted. Idempotent for same (zid, tid).
    On internal error returns 500 with structured error (store does not block participation).
    """
    pool = getattr(request.app.state, "pool", None)
    try:
        return await store(body.zid, body.tid, body.txt, pool)
    except Exception as e:
        logger.exception("store failed: %s", e)
        return error_response(500, "internal_error", detail=None)
