"""OpenAI — announcements, model releases, and research papers."""

from __future__ import annotations

import hashlib
import xml.etree.ElementTree as ET
from typing import Any, ClassVar

import aiohttp

from engine.feeds.normalizer import NormalizedEvent, clamp, parse_timestamp
from engine.feeds.sources.base import FeedError, FeedSource, USER_AGENT


class OpenAIAnnouncements(FeedSource):
    """Monitorea anuncios, lanzamientos de modelos e investigaciones de OpenAI."""

    name: ClassVar[str] = "OpenAI-Announcements"
    domain: ClassVar[str] = "technology"
    event_type: ClassVar[str] = "ai_announcement"
    endpoint: ClassVar[str] = "https://openai.com/api/announcements/rss.xml"

    async def fetch(self, session: aiohttp.ClientSession) -> list[NormalizedEvent]:
        """Descarga e interpreta RSS. Lanza `FeedError` si algo va mal."""
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
        """Parsea RSS de anuncios de OpenAI."""
        events = []
        try:
            root = ET.fromstring(payload)
        except ET.ParseError:
            return []

        # Buscar items en el feed RSS
        for item in root.findall(".//item"):
            title_elem = item.find("title")
            title = (title_elem.text or "").strip() if title_elem is not None else ""

            link_elem = item.find("link")
            link = (link_elem.text or "").strip() if link_elem is not None else ""

            description_elem = item.find("description")
            description = (
                (description_elem.text or "").strip() if description_elem is not None else ""
            )

            pub_date_elem = item.find("pubDate")
            pub_date = pub_date_elem.text if pub_date_elem is not None else None

            if not title:
                continue

            # Generar external_id usando hash del link
            if link:
                external_id = hashlib.md5(link.encode()).hexdigest()[:16]
            else:
                external_id = hashlib.md5(title.encode()).hexdigest()[:16]

            events.append(
                NormalizedEvent(
                    source=self.name,
                    event_type=self.event_type,
                    title=title,
                    description=description,
                    url=link,
                    salience=clamp(0.8),
                    event_time=parse_timestamp(pub_date),
                    external_id=external_id,
                    raw={
                        "link": link,
                        "published": pub_date,
                    },
                )
            )

        return events
