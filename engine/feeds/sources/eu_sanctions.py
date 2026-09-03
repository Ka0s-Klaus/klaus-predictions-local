"""EU — lista de sanciones de la Unión Europea."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import ClassVar

import aiohttp

from engine.feeds.normalizer import NormalizedEvent, clamp
from engine.feeds.sources.base import FeedError, FeedSource, USER_AGENT


class EUSanctions(FeedSource):
    """Entradas de sanciones de la UE (Foreign Sanctions Designations)."""

    name: ClassVar[str] = "EU-Sanctions"
    domain: ClassVar[str] = "sanctions"
    event_type: ClassVar[str] = "eu_sanctions"
    endpoint: ClassVar[str] = (
        "https://webgate.ec.europa.eu/fsd/fsf/public/files/xmlFullSanctionsList_1_1/content"
    )

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
        """Parsea XML de sanciones de la UE."""
        events = []
        try:
            root = ET.fromstring(payload)
        except ET.ParseError as exc:
            raise FeedError(f"{self.name}: XML inválido — {exc}") from exc

        # Buscar individuos
        for person in root.findall(".//Person"):
            reg_number = person.get("reg-number")
            if not reg_number:
                # Intenta obtener de subelementos
                reg_elem = person.find(".//reg-number")
                reg_number = reg_elem.text if reg_elem is not None else ""

            # Nombre
            name_elem = person.find(".//name")
            name = (name_elem.text if name_elem is not None else "").strip()

            if not name:
                continue

            # Información adicional
            designation = ""
            desig_elem = person.find(".//designation")
            if desig_elem is not None:
                desig_text = desig_elem.text or ""
                designation = desig_text.strip()

            events.append(
                NormalizedEvent(
                    source=self.name,
                    event_type=self.event_type,
                    title=name,
                    description=designation or "Individual in EU sanctions list",
                    salience=clamp(0.8),
                    external_id=reg_number or name,
                    raw={"reg_number": reg_number, "type": "person"},
                )
            )

        # Buscar entidades
        for entity in root.findall(".//Entity"):
            reg_number = entity.get("reg-number")
            if not reg_number:
                reg_elem = entity.find(".//reg-number")
                reg_number = reg_elem.text if reg_elem is not None else ""

            name_elem = entity.find(".//name")
            name = (name_elem.text if name_elem is not None else "").strip()

            if not name:
                continue

            designation = ""
            desig_elem = entity.find(".//designation")
            if desig_elem is not None:
                desig_text = desig_elem.text or ""
                designation = desig_text.strip()

            events.append(
                NormalizedEvent(
                    source=self.name,
                    event_type=self.event_type,
                    title=name,
                    description=designation or "Entity in EU sanctions list",
                    salience=clamp(0.8),
                    external_id=reg_number or name,
                    raw={"reg_number": reg_number, "type": "entity"},
                )
            )

        return events
