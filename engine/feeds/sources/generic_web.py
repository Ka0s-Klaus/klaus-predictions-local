"""
Fuente genérica parametrizada para consumir fuentes web públicas.

Esta clase permite integrar cualquier fuente web accesible (HTML, JSON API, RSS)
sin necesidad de implementar una clase específica. Las 2,847 fuentes globales
usan esta clase de forma parametrizada.

Modos soportados:
  - HTML: Scraping simple de contenido público (titles, descriptions)
  - JSON API: Endpoints JSON con estructura variable
  - RSS: Feeds RSS/Atom estándares
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any
from xml.etree import ElementTree as ET

import aiohttp

from engine.feeds.normalizer import NormalizedEvent
from engine.feeds.sources import FeedError, FeedSource

logger = logging.getLogger(__name__)


class GenericWebSource(FeedSource):
    """Fuente genérica parametrizada para fuentes globales."""

    def __init__(
        self,
        source_id: str,
        name: str,
        url: str,
        parser_type: str = "html",
        access_type: str = "web",
        country: str = "GLOBAL",
        domain: str = "general",
        reliability_score: float = 75.0,
        max_bytes: int = 20 * 1024 * 1024,
        **kwargs: Any,
    ):
        """
        Args:
            source_id: ID único (ej: global-aemet-00001)
            name: Nombre legible (ej: AEMET)
            url: Endpoint o homepage
            parser_type: "html", "json", "rss"
            access_type: "web", "api", "rss", etc.
            country: Código ISO (ej: ES)
            domain: Dominio Klaus
            reliability_score: Score 0-100
            max_bytes: Tamaño máximo descarga
        """
        super().__init__(max_bytes=max_bytes)
        self.source_id = source_id
        self.name = name  # Atributo de instancia para compatibilidad
        self.domain = domain  # Dominio para normalización
        self.endpoint = url  # FeedSource.fetch() usa self.endpoint
        self.url = url
        self.parser_type = parser_type
        self.access_type = access_type
        self.country = country
        self.reliability_score = reliability_score

    def parse(self, payload: Any) -> list[NormalizedEvent]:
        """
        Convierte respuesta cruda en eventos normalizados.

        Payload es un string con contenido HTML/JSON/XML.
        """
        if isinstance(payload, str):
            content = payload
        else:
            return []

        event = None
        if self.parser_type == "html":
            event = self._parse_html(content)
        elif self.parser_type == "json":
            event = self._parse_json(content)
        elif self.parser_type == "rss":
            event = self._parse_rss(content)
        else:
            logger.warning(f"{self.name}: parser_type desconocido: {self.parser_type}")
            return []

        if not event:
            return []

        # Convierte a NormalizedEvent
        return [
            NormalizedEvent(
                source=self.name,
                domain=self.domain,
                title=event.get("title", f"Update from {self.name}"),
                summary=event.get("description", ""),
                url=event.get("url", self.url),
                published=event.get("timestamp"),
            )
        ]

    async def _request(
        self, session: aiohttp.ClientSession, endpoint: str
    ) -> str:
        """Descarga contenido del endpoint (override del método base)."""
        try:
            async with session.get(
                endpoint,
                timeout=aiohttp.ClientTimeout(total=20),
                headers={
                    "User-Agent": "Klaus-Predictor/2.0 (+https://github.com/asantacana/klaus-predictions-local)",
                },
            ) as response:
                if response.status != 200:
                    raise FeedError(f"{self.name}: HTTP {response.status}")

                content = await response.read()
                if len(content) > self.max_bytes:
                    raise FeedError(
                        f"{self.name}: contenido {len(content)} > {self.max_bytes} max"
                    )

                return content.decode("utf-8", errors="ignore")

        except asyncio.TimeoutError as e:
            raise FeedError(f"{self.name}: timeout") from e
        except FeedError:
            raise
        except Exception as e:
            raise FeedError(f"{self.name}: {type(e).__name__}: {e}") from e

    def _parse_html(self, content: str) -> dict[str, Any] | None:
        """Extrae metadatos de HTML."""
        data = {
            "title": f"Update from {self.name}",
            "description": f"Check {self.name} for latest updates",
            "url": self.url,
        }

        title_match = re.search(r'<meta property="og:title" content="([^"]+)"', content)
        if title_match:
            data["title"] = title_match.group(1)[:200]

        desc_match = re.search(
            r'<meta property="og:description" content="([^"]+)"', content
        )
        if desc_match:
            data["description"] = desc_match.group(1)[:400]

        return data

    def _parse_json(self, content: str) -> dict[str, Any] | None:
        """Parsea JSON genérico."""
        try:
            obj = json.loads(content)
            data = {"title": self.name, "url": self.url}

            if isinstance(obj, list) and len(obj) > 0:
                obj = obj[0]

            if isinstance(obj, dict):
                for key in ["title", "name", "headline"]:
                    if key in obj:
                        data["title"] = str(obj[key])[:200]
                        break

                for key in ["description", "summary", "text"]:
                    if key in obj:
                        data["description"] = str(obj[key])[:400]
                        break

            return data

        except Exception as e:
            logger.warning(f"{self.name}: JSON parse error: {e}")
            return None

    def _parse_rss(self, content: str) -> dict[str, Any] | None:
        """Parsea RSS/Atom."""
        try:
            root = ET.fromstring(content)
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            items = root.findall(".//item") or root.findall(".//atom:entry", ns)

            if not items:
                return None

            item = items[0]
            data = {"title": self.name, "url": self.url}

            title_elem = item.find("title") or item.find("atom:title", ns)
            if title_elem is not None and title_elem.text:
                data["title"] = title_elem.text[:200]

            desc_elem = (
                item.find("description")
                or item.find("summary", ns)
                or item.find("content", ns)
            )
            if desc_elem is not None and desc_elem.text:
                data["description"] = desc_elem.text[:400]

            return data

        except Exception as e:
            logger.warning(f"{self.name}: RSS parse error: {e}")
            return None

    def __repr__(self) -> str:
        return f"<GenericWeb {self.name:20s} ({self.country}) {self.domain}>"
