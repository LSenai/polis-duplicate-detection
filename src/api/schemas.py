"""
Pydantic schemas for API request/response per contracts/openapi.yaml.
JSON-only; consistent structure.
"""

from pydantic import BaseModel, Field


class CheckRequest(BaseModel):
    """POST /check body: conversation id and comment text."""

    zid: int = Field(..., description="Conversation id")
    txt: str = Field(..., min_length=1, max_length=1000, description="Comment text to check")


class SimilarComment(BaseModel):
    """One similar comment in check response."""

    tid: int
    txt: str
    similarity: float
    tier: str = Field(..., pattern="^(block|warn|related)$")


class CheckResponse(BaseModel):
    """POST /check response: tier and list of similar comments."""

    tier: str = Field(..., pattern="^(block|warn|related|allow)$")
    similar_comments: list[SimilarComment] = Field(default_factory=list)


class StoreRequest(BaseModel):
    """POST /store body: conversation id, comment id, and comment text."""

    zid: int = Field(..., description="Conversation id")
    tid: int = Field(..., description="Comment id within conversation")
    txt: str = Field(..., min_length=1, max_length=1000, description="Comment text")


class StoreResponse(BaseModel):
    """POST /store response."""

    success: bool = True
