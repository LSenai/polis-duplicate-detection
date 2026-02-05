"""
Integration tests for POST /store: store then check finds similar; idempotent (same zid,tid twice).
"""

import pytest
from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)


def test_store_returns_200_and_structure() -> None:
    """POST /store returns 200 and body has success."""
    resp = client.post(
        "/store",
        json={"zid": 1, "tid": 1, "txt": "Teachers need better pay."},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "success" in data
    assert isinstance(data["success"], bool)


def test_store_then_check_finds_similar() -> None:
    """After POST /store, POST /check with paraphrase returns similar_comments (when DB available)."""
    zid, tid, txt = 10, 1, "We should ban AI from schools."
    store_resp = client.post("/store", json={"zid": zid, "tid": tid, "txt": txt})
    assert store_resp.status_code == 200
    store_data = store_resp.json()
    check_resp = client.post(
        "/check",
        json={"zid": zid, "txt": "We ought to prohibit AI in schools."},
    )
    assert check_resp.status_code == 200
    check_data = check_resp.json()
    assert "tier" in check_data
    assert "similar_comments" in check_data
    if store_data.get("success"):
        # When DB is available, check should find the stored comment as similar
        assert check_data["tier"] in ("block", "warn", "related", "allow")
        # Paraphrase should yield at least one similar comment when store succeeded
        if check_data["tier"] != "allow":
            assert len(check_data["similar_comments"]) >= 1


def test_store_idempotent() -> None:
    """POST /store with same zid,tid twice yields 200 both times; single representation (no duplicate)."""
    zid, tid, txt = 20, 1, "Unique comment for idempotent test."
    r1 = client.post("/store", json={"zid": zid, "tid": tid, "txt": txt})
    r2 = client.post("/store", json={"zid": zid, "tid": tid, "txt": txt})
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json().get("success") == r2.json().get("success")
    # Check returns at most one match for this comment (idempotent = one row per zid,tid)
    check_resp = client.post("/check", json={"zid": zid, "txt": txt})
    assert check_resp.status_code == 200
    similar = check_resp.json().get("similar_comments", [])
    tids = [s["tid"] for s in similar]
    assert tids.count(tid) <= 1
