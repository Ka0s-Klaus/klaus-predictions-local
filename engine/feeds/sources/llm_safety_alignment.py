"""arXiv AI Safety — AI alignment, safety, and ethics research."""

from __future__ import annotations

import hashlib
import xml.etree.ElementTree as ET
from typing import Any, ClassVar

import aiohttp

from engine.feeds.normalizer import NormalizedEvent, clamp, parse_timestamp
from engine.feeds.sources.base import FeedError, FeedSource, USER_AGENT


class LLMSafetyAlignment(FeedSource):
    """Monitorea papers sobre seguridad y alineación de IA en arXiv."""

    name: ClassVar[str] = "LLM-Safety-Alignment"
    domain: ClassVar[str] = "research"
    event_type: ClassVar[str] = "ai_safety_research"
    # arXiv category cs.CY es Computers and Society (AI ethics/safety)
    endpoint: ClassVar[str] = "http://arxiv.org/rss/cs.CY"

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
        """Parsea RSS de arXiv para papers de seguridad."""
        events = []
        try:
            root = ET.fromstring(payload)
        except ET.ParseError:
            return []

        # Buscar items en el feed Atom
        for item in root.findall(".//{http://www.w3.org/2005/Atom}entry"):
            title_elem = item.find("{http://www.w3.org/2005/Atom}title")
            title = (title_elem.text or "").strip() if title_elem is not None else ""

            # Buscar el link principal
            link = ""
            for link_elem in item.findall("{http://www.w3.org/2005/Atom}link"):
                href = link_elem.get("href", "")
                if href and "arxiv.org" in href:
                    link = href
                    break

            summary_elem = item.find("{http://www.w3.org/2005/Atom}summary")
            summary = (summary_elem.text or "").strip() if summary_elem is not None else ""

            published_elem = item.find("{http://www.w3.org/2005/Atom}published")
            published = published_elem.text if published_elem is not None else None

            if not title:
                continue

            # Filtrar por palabras clave de seguridad/alineación
            safety_keywords = [
                "safety",
                "alignment",
                "ethics",
                "adversarial",
                "robustness",
                "bias",
                "fairness",
                "transparency",
                "interpretability",
            ]
            title_lower = title.lower()
            summary_lower = summary.lower()

            is_safety_related = any(
                keyword in title_lower or keyword in summary_lower for keyword in safety_keywords
            )

            # Si no tiene keywords claras, aún incluimos pero con salience menor
            if not is_safety_related:
                # Solo incluir si tiene relevancia potencial
                continue

            # Extraer arXiv ID
            arxiv_id = ""
            if "arxiv.org/abs/" in link:
                arxiv_id = link.split("arxiv.org/abs/")[-1]
            else:
                arxiv_id = hashlib.md5(title.encode()).hexdigest()[:12]

            events.append(
                NormalizedEvent(
                    source=self.name,
                    event_type=self.event_type,
                    title=title,
                    description=summary[:500] if summary else None,
                    url=link,
                    salience=clamp(0.8),
                    event_time=parse_timestamp(published),
                    external_id=arxiv_id,
                    raw={
                        "arxiv_id": arxiv_id,
                        "link": link,
                    },
                )
            )

        return events
