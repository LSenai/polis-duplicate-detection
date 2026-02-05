"""
Unit tests for embedding generation: output shape 384, deterministic for same input.
Per constitution: deterministic and reproducible behavior.
"""

import pytest

from src.services.embedding import generate_embedding

# all-MiniLM-L6-v2 output dimension (no magic number in production; test documents expectation).
EXPECTED_DIM = 384


def test_embedding_shape_384() -> None:
    """generate_embedding returns list of length 384."""
    text = "Teachers need better pay."
    out = generate_embedding(text)
    assert isinstance(out, list)
    assert len(out) == EXPECTED_DIM
    assert all(isinstance(x, float) for x in out)


def test_embedding_deterministic() -> None:
    """Same input -> same embedding (no randomness)."""
    text = "We should ban AI from schools."
    a = generate_embedding(text)
    b = generate_embedding(text)
    assert a == b


def test_embedding_different_input_different_output() -> None:
    """Different input -> different embedding."""
    a = generate_embedding("Hello world")
    b = generate_embedding("Different text")
    assert a != b
