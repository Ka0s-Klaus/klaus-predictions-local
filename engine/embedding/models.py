"""Caché de motores de embedding.

Cargar el modelo cuesta segundos y varios cientos de MB. En una máquina de
16 GB no puede haber dos copias por descuido.
"""

from __future__ import annotations

from engine.config import get_settings
from engine.embedding.gpu_engine import GPUEmbeddingEngine

_engines: dict[tuple[str, bool, str], GPUEmbeddingEngine] = {}


def get_engine(
    model_name: str | None = None,
    *,
    use_gpu: bool | None = None,
    device: str | None = None,
) -> GPUEmbeddingEngine:
    """Devuelve el motor compartido para esa combinación de parámetros."""
    settings = get_settings().gpu
    key = (
        model_name or settings.embedding_model,
        settings.use_gpu if use_gpu is None else use_gpu,
        device or settings.device,
    )
    if key not in _engines:
        _engines[key] = GPUEmbeddingEngine(key[0], use_gpu=key[1], device=key[2])
    return _engines[key]


def reset_cache() -> None:
    """Libera los motores cargados. Para tests y para recuperar memoria."""
    _engines.clear()
