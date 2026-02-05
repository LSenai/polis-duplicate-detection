"""
Unit tests for threshold config: named constants, no magic numbers.
Per constitution: thresholds must be explicit and configurable.
"""

import pytest

from src.config import settings


def test_threshold_constants_exist() -> None:
    """THRESHOLD_BLOCK, THRESHOLD_WARN, THRESHOLD_RELATED are defined."""
    assert hasattr(settings, "THRESHOLD_BLOCK")
    assert hasattr(settings, "THRESHOLD_WARN")
    assert hasattr(settings, "THRESHOLD_RELATED")


def test_thresholds_are_floats() -> None:
    """Thresholds are numeric (float)."""
    assert isinstance(settings.THRESHOLD_BLOCK, float)
    assert isinstance(settings.THRESHOLD_WARN, float)
    assert isinstance(settings.THRESHOLD_RELATED, float)


def test_thresholds_in_valid_range() -> None:
    """Thresholds in [0, 1] for similarity scores."""
    assert 0 <= settings.THRESHOLD_BLOCK <= 1
    assert 0 <= settings.THRESHOLD_WARN <= 1
    assert 0 <= settings.THRESHOLD_RELATED <= 1


def test_threshold_ordering() -> None:
    """block >= warn >= related (conservative: block is highest bar)."""
    assert settings.THRESHOLD_BLOCK >= settings.THRESHOLD_WARN
    assert settings.THRESHOLD_WARN >= settings.THRESHOLD_RELATED
