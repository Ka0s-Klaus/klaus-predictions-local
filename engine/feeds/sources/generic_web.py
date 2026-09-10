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

import logging
from typing import Any

import aiohttp

from engine.feeds.sources import FeedError, FeedSource

logger = logging.getLogger(__name__)


class GenericWebSource(FeedSource):
    """Fuente genérica para cualquier endpoint web público."""

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
            source_id: ID único de la fuente (ej: es-aemet-00001)
            name: Nombre legible (ej: AEMET)
            url: URL del endpoint o homepage
            parser_type: "html", "json", "rss"
            access_type: "web", "api", "rss", "data_portal", "dashboard"
            country: Código ISO del país (ej: ES)
            domain: Dominio Klaus (ej: weather, markets, cyber)
            reliability_score: Score de confiabilidad 0-100
            max_bytes: Tamaño máximo de descarga en bytes
        """
        super().__init__(max_bytes=max_bytes)
        self.source_id = source_id
        self.name = name
        self.url = url
        self.parser_type = parser_type
        self.access_type = access_type
        self.country = country
        self.domain = domain
        self.reliability_score = reliability_score

    async def fetch(self, session: aiohttp.ClientSession) -> str | None:
        """Descarga contenido del endpoint."""
        try:
            async with session.get(
                self.url,
                timeout=aiohttp.ClientTimeout(total=20),
                headers={
                    "User-Agent": "Klaus-Predictor/2.0 (+https://github.com/asantacana/klaus-predictions-local)",
                },
            ) as response:
                if response.status != 200:
                    logger.warning(f"{self.name} ({self.country}): HTTP {response.status}")
                    return None

                content = await response.read()
                if len(content) > self.max_bytes:
                    logger.warning(
                        f"{self.name}: contenido {len(content)} bytes > {self.max_bytes} max"
                    )
                    return None

                return content.decode("utf-8", errors="ignore")

        except asyncio.TimeoutError:
            logger.warning(f"{self.name}: timeout")
            raise FeedError(f"{self.name}: timeout después de 20s")
        except Exception as e:
            logger.warning(f"{self.name}: {type(e).__name__}: {e}")
            raise FeedError(f"{self.name}: {e}")

    async def ingest(
        self, session: aiohttp.ClientSession
    ) -> dict[str, Any] | None:
        """Ingesta y normaliza contenido."""
        content = await self.fetch(session)
        if content is None:
            return None

        if self.parser_type == "html":
            return self._parse_html(content)
        elif self.parser_type == "json":
            return self._parse_json(content)
        elif self.parser_type == "rss":
            return self._parse_rss(content)
        else:
            logger.warning(f"{self.name}: parser_type desconocido: {self.parser_type}")
            return None

    def _parse_html(self, content: str) -> dict[str, Any] | None:
        """Extrae metadatos básicos de HTML (og:title, og:description)."""
        import re

        data = {
            "source": self.name,
            "source_id": self.source_id,
            "url": self.url,
            "country": self.country,
            "domain": self.domain,
            "title": "Update from " + self.name,
            "description": f"Check {self.name} for latest updates from {self.country}",
            "reliability": self.reliability_score,
            "timestamp": None,
        }

        # Intenta extraer og:title
        title_match = re.search(r'<meta property="og:title" content="([^"]+)"', content)
        if title_match:
            data["title"] = title_match.group(1)[:200]

        # Intenta extraer og:description
        desc_match = re.search(
            r'<meta property="og:description" content="([^"]+)"', content
        )
        if desc_match:
            data["description"] = desc_match.group(1)[:400]

        return data

    def _parse_json(self, content: str) -> dict[str, Any] | None:
        """Parsea JSON genérico y extrae estructura."""
        import json

        try:
            obj = json.loads(content)

            # Estructura esperada (genérica)
            data = {
                "source": self.name,
                "source_id": self.source_id,
                "url": self.url,
                "country": self.country,
                "domain": self.domain,
                "raw": obj,
                "reliability": self.reliability_score,
            }

            # Si es array, toma el primer elemento
            if isinstance(obj, list) and len(obj) > 0:
                obj = obj[0]

            # Intenta extraer campos comunes
            if isinstance(obj, dict):
                # Busca título
                for key in ["title", "name", "headline", "subject"]:
                    if key in obj:
                        data["title"] = str(obj[key])[:200]
                        break

                # Busca descripción
                for key in ["description", "summary", "text", "content", "body"]:
                    if key in obj:
                        data["description"] = str(obj[key])[:400]
                        break

                # Busca timestamp
                for key in ["timestamp", "date", "published", "created_at", "updated_at"]:
                    if key in obj:
                        data["timestamp"] = obj[key]
                        break

            return data

        except json.JSONDecodeError as e:
            logger.warning(f"{self.name}: JSON inválido: {e}")
            return None

    def _parse_rss(self, content: str) -> dict[str, Any] | None:
        """Parsea RSS/Atom genérico."""
        import re
        from xml.etree import ElementTree as ET

        try:
            root = ET.fromstring(content)

            # Busca primer item/entry
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            items = root.findall(".//item") or root.findall(".//atom:entry", ns)

            if not items:
                return None

            item = items[0]

            data = {
                "source": self.name,
                "source_id": self.source_id,
                "url": self.url,
                "country": self.country,
                "domain": self.domain,
                "reliability": self.reliability_score,
            }

            # Extrae título
            title_elem = item.find("title") or item.find("atom:title", ns)
            if title_elem is not None and title_elem.text:
                data["title"] = title_elem.text[:200]

            # Extrae descripción
            desc_elem = item.find("description") or item.find(
                "summary", ns
            ) or item.find("content", ns)
            if desc_elem is not None and desc_elem.text:
                data["description"] = desc_elem.text[:400]

            # Extrae pubDate
            pub_elem = item.find("pubDate") or item.find("published", ns)
            if pub_elem is not None and pub_elem.text:
                data["timestamp"] = pub_elem.text

            return data

        except ET.ParseError as e:
            logger.warning(f"{self.name}: XML inválido: {e}")
            return None

    def __repr__(self) -> str:
        return f"<GenericWeb {self.name:20s} ({self.country}) {self.domain}>"


import asyncio
