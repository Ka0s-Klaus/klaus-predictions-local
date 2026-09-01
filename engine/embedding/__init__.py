"""Embeddings semánticos, con GPU si la hay."""

from engine.embedding.gpu_engine import (
    EMBEDDING_DIM,
    EmbeddingUnavailableError,
    GPUEmbeddingEngine,
    resolve_device,
)
from engine.embedding.models import get_engine, reset_cache

__all__ = [
    "EMBEDDING_DIM",
    "EmbeddingUnavailableError",
    "GPUEmbeddingEngine",
    "get_engine",
    "reset_cache",
    "resolve_device",
]
