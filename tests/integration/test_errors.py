"""
Integration tests for User Story 3: 4xx on invalid input; allow-shaped on DB/errors.
T029: POST /check missing zid or txt → 4xx with consistent error body.
T030: POST /store missing zid, tid, or txt → 4xx.
T031: DB unavailable or timeout → POST /check returns allow-shaped (tier=allow, similar_comments=[]).
T032: Uncaught exception in /check path → allow-shaped (no 5xx that caller could interpret as block).
"""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)


# --- T029: POST /check with missing zid or txt returns 4xx with consistent error body ---


def test_check_missing_zid_returns_4xx() -> None:
    """POST /check without zid returns 422 with error and detail."""
    resp = client.post("/check", json={"txt": "Hello"})
    assert resp.status_code == 422
    data = resp.json()
    assert "error" in data
    assert data["error"] == "validation_error"
    assert "detail" in data


def test_check_missing_txt_returns_4xx() -> None:
    """POST /check without txt returns 422 with consistent error body."""
    resp = client.post("/check", json={"zid": 1})
    assert resp.status_code == 422
    data = resp.json()
    assert data.get("error") == "validation_error"
    assert "detail" in data


def test_check_empty_txt_returns_4xx() -> None:
    """POST /check with empty txt (min_length=1) returns 422."""
    resp = client.post("/check", json={"zid": 1, "txt": ""})
    assert resp.status_code == 422
    data = resp.json()
    assert data.get("error") == "validation_error"


def test_check_empty_body_returns_4xx() -> None:
    """POST /check with empty body returns 422."""
    resp = client.post("/check", json={})
    assert resp.status_code == 422
    data = resp.json()
    assert "error" in data
    assert data["error"] == "validation_error"


# --- T030: POST /store with missing zid, tid, or txt returns 4xx ---


def test_store_missing_zid_returns_4xx() -> None:
    """POST /store without zid returns 422."""
    resp = client.post("/store", json={"tid": 1, "txt": "Hello"})
    assert resp.status_code == 422
    data = resp.json()
    assert data.get("error") == "validation_error"


def test_store_missing_tid_returns_4xx() -> None:
    """POST /store without tid returns 422."""
    resp = client.post("/store", json={"zid": 1, "txt": "Hello"})
    assert resp.status_code == 422
    data = resp.json()
    assert data.get("error") == "validation_error"


def test_store_missing_txt_returns_4xx() -> None:
    """POST /store without txt returns 422."""
    resp = client.post("/store", json={"zid": 1, "tid": 1})
    assert resp.status_code == 422
    data = resp.json()
    assert data.get("error") == "validation_error"


def test_store_empty_txt_returns_4xx() -> None:
    """POST /store with empty txt returns 422."""
    resp = client.post("/store", json={"zid": 1, "tid": 1, "txt": ""})
    assert resp.status_code == 422
    data = resp.json()
    assert data.get("error") == "validation_error"


# --- T031: DB unavailable → POST /check returns allow-shaped ---


def test_check_db_unavailable_returns_allow_shaped() -> None:
    """When app has no DB pool (DB unavailable), POST /check returns 200 with tier=allow, similar_comments=[]."""
    # Ensure lifespan has run (so state exists) by making one request
    client.post("/health")
    original_pool = getattr(client.app.state, "pool", None)
    try:
        client.app.state.pool = None
        resp = client.post("/check", json={"zid": 1, "txt": "Anything"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["tier"] == "allow"
        assert data["similar_comments"] == []
    finally:
        client.app.state.pool = original_pool


def test_check_db_acquire_raises_returns_allow_shaped() -> None:
    """When pool.acquire() raises (e.g. timeout), POST /check returns allow-shaped, not 5xx."""
    @asynccontextmanager
    async def failing_acquire():
        raise RuntimeError("Connection timeout")

    mock_pool = AsyncMock()
    mock_pool.acquire.return_value = failing_acquire()
    client.post("/health")
    original_pool = getattr(client.app.state, "pool", None)
    try:
        client.app.state.pool = mock_pool
        resp = client.post("/check", json={"zid": 1, "txt": "Anything"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["tier"] == "allow"
        assert data["similar_comments"] == []
    finally:
        client.app.state.pool = original_pool


# --- T032: Uncaught exception in /check path → allow-shaped ---


def test_check_internal_exception_returns_allow_shaped() -> None:
    """Any uncaught exception in /check path results in 200 with tier=allow, not 5xx."""
    with patch("src.api.routes.check", side_effect=Exception("Internal failure")):
        resp = client.post("/check", json={"zid": 1, "txt": "Hello"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["tier"] == "allow"
    assert data["similar_comments"] == []
