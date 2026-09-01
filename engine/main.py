"""Punto de entrada del servidor.

    python -m engine.main
"""

from __future__ import annotations

import logging

from engine.api.app import create_app
from engine.config import get_settings

logging.basicConfig(
    level=logging.DEBUG if get_settings().debug else logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
)

app = create_app()


def main() -> None:
    import uvicorn

    settings = get_settings().api
    uvicorn.run(
        "engine.main:app",
        host=settings.host,
        port=settings.port,
        # Un worker por defecto: cada uno duplica el residente del proceso, y
        # en 16 GB con un modelo de 7B cargado no hay margen para dos.
        workers=settings.workers,
        log_level="debug" if get_settings().debug else "info",
    )


if __name__ == "__main__":
    main()
