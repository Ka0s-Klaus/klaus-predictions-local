"""UN — lista consolidada de sanciones de las Naciones Unidas."""

from __future__ import annotations

import hashlib
import xml.etree.ElementTree as ET
from typing import ClassVar

import aiohttp

from engine.feeds.normalizer import NormalizedEvent, clamp, parse_timestamp
from engine.feeds.sources.base import FeedError, FeedSource, USER_AGENT


class UNSanctions(FeedSource):
    """Entradas de sanciones de la ONU (lista consolidada)."""

    name: ClassVar[str] = "UN-Sanctions"
    domain: ClassVar[str] = "sanctions"
    event_type: ClassVar[str] = "un_sanctions"
    endpoint: ClassVar[str] = "https://scsanctions.un.org/resources/xml/en/consolidated.xml"

    async def fetch(self, session: aiohttp.ClientSession) -> list[NormalizedEvent]:
        """Descarga e interpreta XML. Lanza `FeedError` si algo va mal."""
        xml_text = await self._request_text(session, self.endpoint)
        try:
            events = self.parse(xml_text)
        except FeedError:
            raise
        except Exception as exc:
            raise FeedError(f"{self.name}: la respuesta no encaja con el parser: {exc}") from exc
        return events

    async def _request_text(self, session: aiohttp.ClientSession, url: str) -> str:
        """Descarga la respuesta como texto."""
        headers = {"User-Agent": USER_AGENT, **self.headers}
        try:
            async with session.get(url, headers=headers) as response:
                if response.status != 200:
                    body = (await response.text())[:200]
                    raise FeedError(f"{self.name}: HTTP {response.status} — {body}")

                raw = await response.read()
                if len(raw) > self.max_bytes:
                    raise FeedError(
                        f"{self.name}: {len(raw)} bytes superan el límite de {self.max_bytes}"
                    )
                return raw.decode("utf-8", errors="replace")
        except aiohttp.ClientError as exc:
            raise FeedError(f"{self.name}: fallo de red — {exc}") from exc

    def parse(self, payload: str) -> list[NormalizedEvent]:
        """Parsea XML de sanciones de la ONU con namespaces."""
        events = []
        try:
            root = ET.fromstring(payload)
        except ET.ParseError as exc:
            raise FeedError(f"{self.name}: XML inválido — {exc}") from exc

        # Buscar individuos y entidades (wildcards para ignorar namespaces)
        for entity in root.findall(".//INDIVIDUAL"):
            un_id = self._extract_text(entity, ".//UN_ID")
            name = self._extract_text(entity, ".//FIRST_NAME")
            if not un_id or not name:
                continue

            # Información adicional
            last_name = self._extract_text(entity, ".//LAST_NAME")
            designation = self._extract_text(entity, ".//DESIGNATION")

            full_name = f"{name} {last_name}".strip()

            # Descripción
            description = designation or "Individual in UN sanctions list"

            events.append(
                NormalizedEvent(
                    source=self.name,
                    event_type=self.event_type,
                    title=full_name,
                    description=description,
                    salience=clamp(0.8),
                    external_id=un_id,
                    raw={"un_id": un_id, "type": "individual"},
                )
            )

        # También buscar entidades
        for entity in root.findall(".//ENTITY"):
            un_id = self._extract_text(entity, ".//UN_ID")
            name = self._extract_text(entity, ".//NAME")
            if not un_id or not name:
                continue

            designation = self._extract_text(entity, ".//DESIGNATION")
            description = designation or "Entity in UN sanctions list"

            events.append(
                NormalizedEvent(
                    source=self.name,
                    event_type=self.event_type,
                    title=name,
                    description=description,
                    salience=clamp(0.8),
                    external_id=un_id,
                    raw={"un_id": un_id, "type": "entity"},
                )
            )

        return events

    @staticmethod
    def _extract_text(element: ET.Element, path: str) -> str:
        """Extrae texto de un elemento usando findall con wildcards para namespaces."""
        elem = element.find(path)
        if elem is not None and elem.text:
            return elem.text.strip()
        return ""
