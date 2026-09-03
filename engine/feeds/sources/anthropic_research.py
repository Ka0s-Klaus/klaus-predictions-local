"""Anthropic — research publications and model announcements."""

from __future__ import annotations

import hashlib
import xml.etree.ElementTree as ET
from typing import Any, ClassVar

import aiohttp

from engine.feeds.normalizer import NormalizedEvent, clamp, parse_timestamp
from engine.feeds.sources.base import FeedError, FeedSource, USER_AGENT


class AnthropicResearch(FeedSource):
    """Monitorea investigaciones y anuncios de Anthropic."""

    name: ClassVar[str] = "Anthropic-Research"
    domain: ClassVar[str] = "technology"
    event_type: ClassVar[str] = "research_announcement"
    # Usando el feed Atom del blog de Anthropic si está disponible
    endpoint: ClassVar[str] = "https://www.anthropic.com/feed.xml"

    async def fetch(self, session: aiohttp.ClientSession) -> list[NormalizedEvent]:
        """Descarga e interpreta RSS/Atom. Lanza `FeedError` si algo va mal."""
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
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as response:
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
        """Parsea RSS/Atom de Anthropic."""
        events = []
        try:
            root = ET.fromstring(payload)
        except ET.ParseError:
            return []

        # Soporta tanto RSS como Atom
        # Buscar items RSS
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

            # Generar ID
            if link:
                external_id = hashlib.md5(link.encode()).hexdigest()[:16]
            else:
                external_id = hashlib.md5(title.encode()).hexdigest()[:16]

            events.append(
                NormalizedEvent(
                    source=self.name,
                    event_type=self.event_type,
                    title=title,
                    description=description[:500] if description else None,
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

        # También buscar entries Atom en caso de que sea un feed Atom
        for entry in root.findall(".//{http://www.w3.org/2005/Atom}entry"):
            title_elem = entry.find("{http://www.w3.org/2005/Atom}title")
            title = (title_elem.text or "").strip() if title_elem is not None else ""

            link = ""
            for link_elem in entry.findall("{http://www.w3.org/2005/Atom}link"):
                href = link_elem.get("href", "")
                if href:
                    link = href
                    break

            summary_elem = entry.find("{http://www.w3.org/2005/Atom}summary")
            summary = (summary_elem.text or "").strip() if summary_elem is not None else ""

            published_elem = entry.find("{http://www.w3.org/2005/Atom}published")
            published = published_elem.text if published_elem is not None else None

            if not title:
                continue

            external_id = hashlib.md5((link or title).encode()).hexdigest()[:16]

            events.append(
                NormalizedEvent(
                    source=self.name,
                    event_type=self.event_type,
                    title=title,
                    description=summary[:500] if summary else None,
                    url=link,
                    salience=clamp(0.8),
                    event_time=parse_timestamp(published),
                    external_id=external_id,
                    raw={
                        "link": link,
                        "published": published,
                    },
                )
            )

        return events
