"""
Similarity tier classification: map score to block/warn/related/allow.
Single-purpose, documented; uses named threshold constants (no magic numbers).
Per constitution: thresholds explicit and configurable; composable pipeline.
"""

from typing import Literal

Tier = Literal["block", "warn", "related", "allow"]


def classify_tier(
    score: float,
    *,
    threshold_block: float,
    threshold_warn: float,
    threshold_related: float,
) -> Tier:
    """
    Classify a similarity score into a tier for caller policy.
    Boundaries: block >= threshold_block, warn >= threshold_warn, related >= threshold_related.
    """
    if score >= threshold_block:
        return "block"
    if score >= threshold_warn:
        return "warn"
    if score >= threshold_related:
        return "related"
    return "allow"
