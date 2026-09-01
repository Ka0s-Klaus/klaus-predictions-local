"""Clase base de las fuentes de datos.

Una fuente sabe tres cosas: de dónde bajar, cómo interpretar lo que baja y qué
relevancia (`salience`) asignar a cada evento. Todo lo demás — concurrencia,
tiempos de espera, deduplicación — lo pone el ingestor.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, ClassVar

import aiohttp

from engine.feeds.normalizer import NormalizedEvent

logger = logging.getLogger(__name__)

# Estas APIs públicas piden identificarse. api.weather.gov rechaza las
# peticiones sin User-Agent reconocible.
USER_AGENT = "pythia-oracle/0.1 (+https://github.com/Ka0s-Klaus/klaus-predictions-local)"


class FeedError(RuntimeError):
    """La fuente no pudo entregar datos utilizables."""


class FeedSource(ABC):
    """Contrato de una fuente."""

    name: ClassVar[str]
    domain: ClassVar[str]
    event_type: ClassVar[str]
    endpoint: ClassVar[str]
    #: Cabeceras propias de la fuente, además del User-Agent.
    headers: ClassVar[dict[str, str]] = {}

    def __init__(self, max_bytes: int = 20 * 1024 * 1024) -> None:
        self.max_bytes = max_bytes

    def __repr__(self) -> str:
        return f"<{type(self).__name__} {self.name}>"

    @abstractmethod
    def parse(self, payload: Any) -> list[NormalizedEvent]:
        """Convierte la respuesta cruda en eventos normalizados."""

    async def fetch(self, session: aiohttp.ClientSession) -> list[NormalizedEvent]:
        """Descarga e interpreta. Lanza `FeedError` si algo va mal."""
        payload = await self._request(session, self.endpoint)
        try:
            events = self.parse(payload)
        except FeedError:
            raise
        except Exception as exc:
            # Un cambio de formato en la fuente no puede tumbar la ingesta entera.
            raise FeedError(f"{self.name}: la respuesta no encaja con el parser: {exc}") from exc
        logger.debug("%s devolvió %d eventos", self.name, len(events))
        return events

    async def _request(self, session: aiohttp.ClientSession, url: str) -> Any:
        headers = {"User-Agent": USER_AGENT, **self.headers}
        try:
            async with session.get(url, headers=headers) as response:
                if response.status != 200:
                    body = (await response.text())[:200]
                    raise FeedError(f"{self.name}: HTTP {response.status} — {body}")

                # Cortar por tamaño antes de leer: un feed que se descontrola no
                # puede llevarse por delante una máquina de 16 GB.
                declared = response.content_length
                if declared is not None and declared > self.max_bytes:
                    raise FeedError(
                        f"{self.name}: la respuesta declara {declared} bytes, "
                        f"por encima del límite de {self.max_bytes}"
                    )

                raw = await response.read()
                if len(raw) > self.max_bytes:
                    raise FeedError(
                        f"{self.name}: {len(raw)} bytes superan el límite de {self.max_bytes}"
                    )
                # Varias de estas APIs sirven JSON con content-type raro
                # (`application/geo+json`, `text/plain`), de ahí content_type=None.
                return await response.json(content_type=None)
        except aiohttp.ClientError as exc:
            raise FeedError(f"{self.name}: fallo de red — {exc}") from exc
        except ValueError as exc:
            raise FeedError(f"{self.name}: la respuesta no es JSON válido — {exc}") from exc
