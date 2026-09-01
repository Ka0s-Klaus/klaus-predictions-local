"""Capa de embeddings con aceleración opcional.

La especificación pedía `SentenceTransformer(..., device="cuda")` para una Intel
HD 520/530. Esas GPU no tienen CUDA: la llamada falla en cuanto se toca. Aquí el
dispositivo se **resuelve probando** lo que existe de verdad en la máquina, y se
degrada a CPU con un aviso en lugar de reventar.

Sobre la memoria: en gráficos integrados la "VRAM" es RAM del sistema
compartida. Mover los embeddings a la iGPU descarga la CPU, pero **no libera un
solo byte** del presupuesto de 16 GB. Ver `docs/HARDWARE.md`.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    import numpy as np

logger = logging.getLogger(__name__)

# Dimensión de all-MiniLM-L6-v2, el modelo por defecto.
EMBEDDING_DIM = 384


class EmbeddingUnavailableError(RuntimeError):
    """Falta el extra opcional de embeddings."""


@lru_cache(maxsize=1)
def resolve_device(preference: str = "auto") -> str:
    """Elige el mejor dispositivo disponible.

    Orden: preferencia explícita → XPU de Intel (vía IPEX) → CUDA → CPU.
    Nunca lanza: si nada está disponible, devuelve ``"cpu"``.
    """
    if preference not in ("auto", "gpu", ""):
        return preference

    try:
        import torch
    except ImportError:
        logger.info("torch no está instalado; los embeddings irán por CPU")
        return "cpu"

    # Intel Arc / Xe / iGPU recientes a través de intel-extension-for-pytorch.
    if hasattr(torch, "xpu") and torch.xpu.is_available():
        logger.info("Embeddings sobre XPU de Intel")
        return "xpu"

    if torch.cuda.is_available():
        logger.info("Embeddings sobre CUDA")
        return "cuda"

    logger.info(
        "Sin GPU utilizable para embeddings; se usa CPU. "
        "En una Intel HD 520/530 esto es lo normal: no tiene backend de PyTorch."
    )
    return "cpu"


class GPUEmbeddingEngine:
    """Envoltorio sobre sentence-transformers con carga perezosa."""

    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        *,
        use_gpu: bool = False,
        device: str = "auto",
    ) -> None:
        self.model_name = model_name
        self.device = resolve_device(device) if use_gpu else "cpu"
        self._model: Any | None = None

    @property
    def model(self) -> Any:
        """Carga el modelo la primera vez que se necesita.

        Importar sentence-transformers arrastra torch y tarda segundos; hacerlo
        al importar el módulo penalizaría el arranque de toda la aplicación.
        """
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:
                raise EmbeddingUnavailableError(
                    "Los embeddings requieren el extra opcional: "
                    'pip install -e ".[embeddings]"'
                ) from exc
            logger.info("Cargando %s en %s", self.model_name, self.device)
            self._model = SentenceTransformer(self.model_name, device=self.device)
        return self._model

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    def embed(self, texts: list[str]) -> np.ndarray:
        """Vectoriza una lista de textos. Devuelve un array `(N, 384)`."""
        if not texts:
            import numpy as np

            return np.empty((0, EMBEDDING_DIM), dtype="float32")
        return self.model.encode(texts, convert_to_numpy=True, show_progress_bar=False)

    @staticmethod
    def similarity(a: np.ndarray, b: np.ndarray) -> float:
        """Similitud coseno entre dos vectores."""
        import numpy as np

        denominator = float(np.linalg.norm(a) * np.linalg.norm(b))
        if denominator == 0.0:
            return 0.0
        return float(np.dot(a, b) / denominator)
