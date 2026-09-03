"""AI Security Vulnerabilities — adversarial attacks and ML security issues."""

from __future__ import annotations

import hashlib
import xml.etree.ElementTree as ET
from typing import Any, ClassVar

import aiohttp

from engine.feeds.normalizer import NormalizedEvent, clamp, parse_timestamp
from engine.feeds.sources.base import FeedError, FeedSource, USER_AGENT


class AISafetyVulnerabilities(FeedSource):
    """Monitorea vulnerabilidades de seguridad en sistemas de IA."""

    name: ClassVar[str] = "AI-Security-Vulnerabilities"
    domain: ClassVar[str] = "cyber"
    event_type: ClassVar[str] = "ai_security_issue"
    # Usando arXiv cs.CR (Cryptography and Security) con filtro de adversarial
    endpoint: ClassVar[str] = "http://arxiv.org/rss/cs.CR"

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
        """Parsea RSS de arXiv para papers de seguridad en IA."""
        events = []
        try:
            root = ET.fromstring(payload)
        except ET.ParseError:
            return []

        # Palabras clave que indican seguridad en IA
        ai_security_keywords = [
            "adversarial",
            "attack",
            "neural network",
            "deep learning",
            "model",
            "classifier",
            "evasion",
            "poisoning",
            "backdoor",
            "machine learning",
            "ai",
            "llm",
            "prompt injection",
            "jailbreak",
        ]

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

            # Filtrar por palabras clave de seguridad en IA
            title_lower = title.lower()
            summary_lower = summary.lower()

            is_ai_security = any(
                keyword in title_lower or keyword in summary_lower for keyword in ai_security_keywords
            )

            # Solo incluir si es relevante para seguridad en IA
            if not is_ai_security:
                continue

            # Extraer arXiv ID o generar uno
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
                    salience=clamp(0.85),  # Vulnerabilidades de seguridad son críticas
                    event_time=parse_timestamp(published),
                    external_id=arxiv_id,
                    raw={
                        "arxiv_id": arxiv_id,
                        "link": link,
                        "type": "adversarial_research",
                    },
                )
            )

        return events
