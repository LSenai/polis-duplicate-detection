"""
Embedding service: load sentence-transformers all-MiniLM-L6-v2 once (singleton).
Per constitution: model versions must be pinned; no hidden randomness.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Lazy-loaded singleton; loaded on first use to avoid blocking app startup.
_model: Any = None
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


def _get_model() -> Any:
    """Load model once; return cached instance."""
    global _model
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer

            _model = SentenceTransformer(MODEL_NAME)
            logger.info("Loaded embedding model: %s", MODEL_NAME)
        except Exception as e:
            logger.exception("Failed to load embedding model: %s", e)
            raise
    return _model


def generate_embedding(text: str) -> list[float]:
    """
    Generate normalized 384-dim embedding for text.
    Deterministic for same input (no randomness).
    """
    model = _get_model()
    # normalize_embeddings=True for cosine similarity
    arr = model.encode([text], normalize_embeddings=True)
    return arr[0].tolist()
