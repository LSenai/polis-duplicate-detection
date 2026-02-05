"""
Structured error response schema and exception handlers for 4xx.
Per constitution: consistent error structure; invalid input returns structured errors.
"""

import logging
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class ErrorBody(BaseModel):
    """Consistent error shape for all endpoints."""

    error: str
    detail: str | None = None


def error_response(status_code: int, error: str, detail: str | None = None) -> JSONResponse:
    """Return JSONResponse with ErrorBody shape."""
    body = ErrorBody(error=error, detail=detail)
    return JSONResponse(
        status_code=status_code,
        content=body.model_dump(exclude_none=True),
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handle Pydantic validation errors (422) with consistent body."""
    detail = str(exc.errors()) if getattr(exc, "errors", None) else str(exc)
    return error_response(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        error="validation_error",
        detail=detail,
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Log and return 500; do not expose internal details to caller."""
    logger.exception("Unhandled exception: %s", exc)
    return error_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        error="internal_error",
        detail=None,
    )


def register_error_handlers(app: FastAPI) -> None:
    """Register exception handlers on the FastAPI app."""
    app.add_exception_handler(
        RequestValidationError,
        validation_exception_handler,
    )
    app.add_exception_handler(Exception, generic_exception_handler)
