"""GDACS — alertas de desastres en tiempo real."""

from __future__ import annotations

import hashlib
import xml.etree.ElementTree as ET
from typing import Any, ClassVar

import aiohttp

from engine.feeds.normalizer import NormalizedEvent, clamp, parse_timestamp
from engine.feeds.sources.base import FeedError, FeedSource, USER_AGENT


class GDACSDisasters(FeedSource):
    """Alertas de desastres (terremotos, inundaciones, tormentas) de GDACS."""

    name: ClassVar[str] = "GDACS"
    domain: ClassVar[str] = "disasters"
    event_type: ClassVar[str] = "disaster_alert"
    endpoint: ClassVar[str] = "https://www.gdacs.org/xml/rss.xml"

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
        """Parsea RSS XML y extrae eventos de desastres."""
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

            # Generar external_id de link
            external_id = self._hash_id(link)

            # Calcular salience según tipo de desastre
            salience = self._calculate_salience(title, description)

            events.append(
                NormalizedEvent(
                    source=self.name,
                    event_type=self.event_type,
                    title=title,
                    description=description,
                    url=link,
                    salience=salience,
                    event_time=parse_timestamp(pub_date),
                    external_id=external_id,
                    raw={"type": self._extract_type(title)},
                )
            )

        return events

    @staticmethod
    def _hash_id(url: str) -> str:
        """Genera un ID único basado en el URL."""
        if not url:
            return ""
        # Tomar la última parte del URL
        last_part = url.split("/")[-1]
        return hashlib.md5(last_part.encode()).hexdigest()[:16]

    @staticmethod
    def _calculate_salience(title: str, description: str) -> float:
        """Calcula salience basada en tipo de desastre."""
        combined = (title + " " + description).lower()

        if "earthquake" in combined or "terremoto" in combined:
            return clamp(0.9)
        if "flood" in combined or "inundación" in combined:
            return clamp(0.75)
        if "storm" in combined or "tormenta" in combined:
            return clamp(0.7)
        if "volcano" in combined or "volcán" in combined:
            return clamp(0.85)
        if "tsunami" in combined:
            return clamp(0.95)

        return clamp(0.5)

    @staticmethod
    def _extract_type(title: str) -> str:
        """Extrae tipo de desastre del título."""
        title_lower = title.lower()
        if "earthquake" in title_lower or "terremoto" in title_lower:
            return "earthquake"
        if "flood" in title_lower or "inundación" in title_lower:
            return "flood"
        if "storm" in title_lower or "tormenta" in title_lower:
            return "storm"
        if "volcano" in title_lower or "volcán" in title_lower:
            return "volcano"
        if "tsunami" in title_lower:
            return "tsunami"
        return "unknown"
