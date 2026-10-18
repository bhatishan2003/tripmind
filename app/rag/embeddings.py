"""Embeddings via local sentence-transformers (no API key needed).

Default model `all-MiniLM-L6-v2` (dim 384) matches settings.EMBEDDING_DIM.
Offline fallback: deterministic hash-based vectors so ingestion, tests and CI
work without downloading the model or torch.
"""

from __future__ import annotations

import hashlib
import logging
import math
from functools import lru_cache

from app.core.config import settings

logger = logging.getLogger(__name__)

_MODEL_CACHE: dict[str, object] = {}
_FALLBACK_USED = False


def _hash_vector(text: str, dim: int) -> list[float]:
    """Deterministic L2-normalized pseudo-embedding from SHA256 word hashes."""
    vec = [0.0] * dim
    for word in text.lower().split():
        h = int(hashlib.sha256(word.encode()).hexdigest(), 16)
        vec[h % dim] += 1.0
        vec[(h >> 16) % dim] += 0.5
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


def _load_model(name: str):  # type: ignore[no-untyped-def]
    if name in _MODEL_CACHE:
        return _MODEL_CACHE[name]
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(name)
    _MODEL_CACHE[name] = model
    return model


def is_fallback_active() -> bool:
    return _FALLBACK_USED


def embed_texts(
    texts: list[str],
    *,
    model_name: str | None = None,
    dim: int | None = None,
    normalize: bool = True,
) -> list[list[float]]:
    """Embed a batch of texts. Falls back to hash vectors offline."""
    global _FALLBACK_USED
    if not texts:
        return []
    name = model_name or settings.EMBEDDING_MODEL
    dim = dim or settings.EMBEDDING_DIM
    try:
        model = _load_model(name)
        vectors = model.encode(texts, normalize_embeddings=normalize, show_progress_bar=False)
        out = [list(map(float, v)) for v in vectors]
        # Guard against dim mismatch (e.g. swapped model without config change)
        if out and len(out[0]) != dim:
            logger.warning("Embedding dim %d != settings dim %d", len(out[0]), dim)
        return out
    except Exception as exc:  # noqa: BLE001 - offline / no torch / no model cache
        _FALLBACK_USED = True
        logger.warning("sentence-transformers unavailable (%s) — using hash fallback", exc)
        return [_hash_vector(t, dim) for t in texts]


def embed_query(text: str, **kwargs) -> list[float]:  # type: ignore[no-untyped-def]
    return embed_texts([text], **kwargs)[0]


@lru_cache(maxsize=1)
def get_embedding_dim(model_name: str | None = None) -> int:
    """Actual model dim (loads model); falls back to settings dim offline."""
    try:
        model = _load_model(model_name or settings.EMBEDDING_MODEL)
        return int(model.get_sentence_embedding_dimension())
    except Exception:  # noqa: BLE001 - offline fallback is the point
        return settings.EMBEDDING_DIM


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (na * nb)
