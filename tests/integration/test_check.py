"""
Integration test for POST /check: no similar comments -> allow; structure tier + similar_comments.
Conversation-scoped (zid in request).
"""

import pytest
from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)


def test_check_returns_200_and_structure() -> None:
    """POST /check returns 200 and body has tier and similar_comments."""
    resp = client.post("/check", json={"zid": 1, "txt": "Hello world"})
    assert resp.status_code == 200
    data = resp.json()
    assert "tier" in data
    assert "similar_comments" in data
    assert data["tier"] in ("block", "warn", "related", "allow")
    assert isinstance(data["similar_comments"], list)


def test_check_no_similar_returns_allow() -> None:
    """When no similar comments (empty DB or no DB), tier is allow and similar_comments empty."""
    resp = client.post("/check", json={"zid": 99, "txt": "Unique comment with no matches"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["tier"] == "allow"
    assert data["similar_comments"] == []


def test_check_conversation_scoped() -> None:
    """Request includes zid; response is for that conversation only (structure check)."""
    resp = client.post("/check", json={"zid": 42, "txt": "Scoped to conversation 42"})
    assert resp.status_code == 200
    data = resp.json()
    assert "tier" in data
    assert "similar_comments" in data
