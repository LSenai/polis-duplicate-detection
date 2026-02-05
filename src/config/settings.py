"""
Configuration from environment. No inline config; thresholds and DATABASE_URL from env.
Per constitution: thresholds must be explicit and configurable.
"""

import os


def _float_env(name: str, default: float) -> float:
    """Read float from environment; return default if unset or invalid."""
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def get_database_url() -> str | None:
    """DATABASE_URL for PostgreSQL (with pgvector)."""
    return os.environ.get("DATABASE_URL")


# Named constants for similarity tiers (no magic numbers).
# Defaults per spec/research; MUST be validated and tested.
THRESHOLD_BLOCK: float = _float_env("THRESHOLD_BLOCK", 0.93)
THRESHOLD_WARN: float = _float_env("THRESHOLD_WARN", 0.88)
THRESHOLD_RELATED: float = _float_env("THRESHOLD_RELATED", 0.75)

# Optional: recommended timeout for /check (seconds), advertised in API docs.
CHECK_TIMEOUT_RECOMMENDED_SEC: int = int(_float_env("CHECK_TIMEOUT_RECOMMENDED", 2.0))

# DB connection timeout (seconds); constitution: all external calls must have timeouts.
DB_TIMEOUT_SEC: float = _float_env("DB_TIMEOUT_SEC", 5.0)
