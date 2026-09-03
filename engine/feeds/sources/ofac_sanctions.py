"""OFAC — lista de sanciones del Departamento del Tesoro de los EE.UU."""

from __future__ import annotations

import hashlib
import xml.etree.ElementTree as ET
from typing import ClassVar

import aiohttp

from engine.feeds.normalizer import NormalizedEvent, clamp, parse_timestamp
from engine.feeds.sources.base import FeedError, FeedSource, USER_AGENT


class OFACSanctions(FeedSource):
    """Entradas de sanciones de OFAC (Office of Foreign Assets Control)."""

    name: ClassVar[str] = "OFAC"
    domain: ClassVar[str] = "sanctions"
    event_type: ClassVar[str] = "sanctions_entry"
    endpoint: ClassVar[str] = "https://sanctionslist.ofac.treas.gov/Home/SdnList"

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
        """Parsea XML de sanciones OFAC."""
        events = []

        # El endpoint puede devolver HTML con XML embebido o XML directo
        xml_text = self._extract_xml(payload)

        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as exc:
            raise FeedError(f"{self.name}: XML inválido — {exc}") from exc

        # Buscar registros de entidades o individuos
        for entry in root.findall(".//entry"):
            uid_elem = entry.find(".//uid")
            uid = uid_elem.text if uid_elem is not None else ""

            name_elem = entry.find(".//name")
            name = (name_elem.text if name_elem is not None else "").strip()

            if not name:
                continue

            # Extraer información adicional
            title_field = entry.find(".//title")
            title_text = (title_field.text if title_field is not None else "").strip()

            designation_elem = entry.find(".//designation")
            designation = (designation_elem.text if designation_elem is not None else "").strip()

            # Generar external_id
            external_id = uid or self._generate_id(name)

            # Construir descripción
            description = f"{title_text}" if title_text else "Sanctions Entry"
            if designation:
                description = f"{description} | {designation}".strip(" |")

            events.append(
                NormalizedEvent(
                    source=self.name,
                    event_type=self.event_type,
                    title=name,
                    description=description,
                    salience=clamp(0.8),  # Todas las sanciones OFAC son significativas
                    external_id=external_id,
                    raw={"uid": uid, "designation": designation},
                )
            )

        return events

    @staticmethod
    def _extract_xml(html_or_xml: str) -> str:
        """Intenta extraer XML de HTML embebido o retorna el texto tal cual."""
        # Si ya es XML, retornar tal cual
        if html_or_xml.strip().startswith("<?xml") or html_or_xml.strip().startswith("<"):
            return html_or_xml

        # Buscar CDATA o XML embebido en HTML
        import re

        # Buscar CDATA sections
        cdata_pattern = r"<!\[CDATA\[(.*?)\]\]>"
        matches = re.findall(cdata_pattern, html_or_xml, re.DOTALL)
        if matches:
            return matches[0]

        # Buscar cualquier contenido XML
        xml_pattern = r"(<[^>]+>.*?</[^>]+>)"
        matches = re.findall(xml_pattern, html_or_xml, re.DOTALL)
        if matches:
            return matches[0]

        # Si no hay nada obvio, retornar el original
        return html_or_xml

    @staticmethod
    def _generate_id(name: str) -> str:
        """Genera ID único basado en el nombre."""
        return hashlib.md5(name.encode()).hexdigest()[:16]
