"""Smithsonian GVP — reporte semanal de actividad volcánica."""

from __future__ import annotations

import hashlib
import xml.etree.ElementTree as ET
from typing import ClassVar

import aiohttp

from engine.feeds.normalizer import NormalizedEvent, clamp, parse_timestamp
from engine.feeds.sources.base import FeedError, FeedSource, USER_AGENT


class SmithsonianVolcano(FeedSource):
    """Actividad volcánica del Global Volcanism Program (GVP)."""

    name: ClassVar[str] = "GVP"
    domain: ClassVar[str] = "disasters"
    event_type: ClassVar[str] = "volcano_activity"
    endpoint: ClassVar[str] = (
        "https://volcano.si.edu/news/WeeklyVolcanoActivityReport_Syndication.cfm"
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
        """Parsea RSS XML y extrae eventos de actividad volcánica."""
        events = []
        try:
            root = ET.fromstring(payload)
        except ET.ParseError as exc:
            raise FeedError(f"{self.name}: XML inválido — {exc}") from exc

        for item in root.findall(".//item"):
            title = (item.findtext("title") or "").strip()
            description = (item.findtext("description") or "").strip()
            link = item.findtext("link") or ""
            pub_date = item.findtext("pubDate")

            if not title:
                continue

            # Extraer nombre del volcán del título
            volcano_name = self._extract_volcano_name(title)

            # Generar external_id
            external_id = self._generate_id(volcano_name, pub_date)

            events.append(
                NormalizedEvent(
                    source=self.name,
                    event_type=self.event_type,
                    title=title,
                    description=description,
                    url=link,
                    salience=clamp(0.6),  # Actividad volcánica siempre es relevante
                    event_time=parse_timestamp(pub_date),
                    external_id=external_id,
                    raw={"volcano": volcano_name},
                )
            )

        return events

    @staticmethod
    def _extract_volcano_name(title: str) -> str:
        """Extrae el nombre del volcán del título."""
        # Típicamente el formato es "Volcano Name Activity Report"
        # Intentamos extraer la primera parte
        parts = title.split("Activity")
        if parts:
            return parts[0].strip()
        return title.strip()

    @staticmethod
    def _generate_id(volcano_name: str, pub_date: str | None) -> str:
        """Genera ID único basado en nombre del volcán y fecha."""
        combined = f"{volcano_name}_{pub_date or ''}"
        return hashlib.md5(combined.encode()).hexdigest()[:16]
