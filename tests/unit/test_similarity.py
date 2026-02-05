"""
Unit tests for similarity tier classification (block/warn/related/allow).
Real text examples and threshold boundaries per constitution.
"""

import pytest

from src.services.similarity import classify_tier


# Use explicit thresholds in tests (no magic numbers); boundaries from spec/research.
BLOCK = 0.93
WARN = 0.88
RELATED = 0.75


def test_classify_block_at_boundary() -> None:
    """Score exactly at block threshold -> block."""
    assert classify_tier(0.93, threshold_block=BLOCK, threshold_warn=WARN, threshold_related=RELATED) == "block"
    assert classify_tier(1.0, threshold_block=BLOCK, threshold_warn=WARN, threshold_related=RELATED) == "block"


def test_classify_warn_below_block_above_warn() -> None:
    """Score in [warn, block) -> warn."""
    assert classify_tier(0.88, threshold_block=BLOCK, threshold_warn=WARN, threshold_related=RELATED) == "warn"
    assert classify_tier(0.92, threshold_block=BLOCK, threshold_warn=WARN, threshold_related=RELATED) == "warn"


def test_classify_related_below_warn_above_related() -> None:
    """Score in [related, warn) -> related."""
    assert classify_tier(0.75, threshold_block=BLOCK, threshold_warn=WARN, threshold_related=RELATED) == "related"
    assert classify_tier(0.87, threshold_block=BLOCK, threshold_warn=WARN, threshold_related=RELATED) == "related"


def test_classify_allow_below_related() -> None:
    """Score below related -> allow (distinct opinions)."""
    assert classify_tier(0.74, threshold_block=BLOCK, threshold_warn=WARN, threshold_related=RELATED) == "allow"
    assert classify_tier(0.0, threshold_block=BLOCK, threshold_warn=WARN, threshold_related=RELATED) == "allow"


def test_classify_boundary_between_related_and_allow() -> None:
    """Just below related (e.g. distinct opinions like Ban AI vs Ban screens) -> allow."""
    assert classify_tier(0.74, threshold_block=BLOCK, threshold_warn=WARN, threshold_related=RELATED) == "allow"
