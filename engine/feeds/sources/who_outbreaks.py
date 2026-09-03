"""WHO — alertas de brotes de enfermedades (Disease Outbreak News)."""

from __future__ import annotations

import hashlib
import re
import xml.etree.ElementTree as ET
from typing import ClassVar

import aiohttp

from engine.feeds.normalizer import NormalizedEvent, clamp, parse_timestamp
from engine.feeds.sources.base import FeedError, FeedSource, USER_AGENT


class WHOOutbreaks(FeedSource):
    """Alertas de brotes de enfermedades de la Organización Mundial de la Salud."""

    name: ClassVar[str] = "WHO"
    domain: ClassVar[str] = "health"
    event_type: ClassVar[str] = "disease_outbreak"
    endpoint: ClassVar[str] = "https://www.who.int/feeds/entity/csr/don/en/rss.xml"

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
        """Parsea RSS XML y extrae eventos de brotes de enfermedades."""
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

            # Generar external_id basado en link y fecha
            external_id = self._generate_id(link, pub_date)

            # Calcular salience: 0.7 base, más si hay muertes mencionadas
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
                    raw={"deaths_mentioned": self._has_death_mention(description)},
                )
            )

        return events

    @staticmethod
    def _generate_id(link: str, pub_date: str | None) -> str:
        """Genera ID único basado en link y fecha."""
        combined = f"{link}_{pub_date or ''}"
        return hashlib.md5(combined.encode()).hexdigest()[:16]

    @staticmethod
    def _calculate_salience(title: str, description: str) -> float:
        """Calcula salience basada en presencia de muertes y tipo de enfermedad."""
        combined = (title + " " + description).lower()

        salience = 0.7

        # Aumentar si hay menciones de muertes
        if any(keyword in combined for keyword in ["death", "deaths", "died", "muerto"]):
            salience = clamp(salience + 0.15)

        # Aumentar para enfermedades graves o epidemias conocidas
        high_risk_diseases = [
            "ebola",
            "plague",
            "cholera",
            "yellow fever",
            "dengue",
            "mpox",
            "covid",
            "coronavirus",
        ]
        if any(disease in combined for disease in high_risk_diseases):
            salience = clamp(salience + 0.1)

        return clamp(salience)

    @staticmethod
    def _has_death_mention(description: str) -> bool:
        """Verifica si hay mención de muertes en la descripción."""
        death_patterns = [
            r"\d+\s*(death|deaths|muerto|muertos|fallecido)",
            r"death toll",
            r"fatalities",
            r"fatal",
        ]
        for pattern in death_patterns:
            if re.search(pattern, description, re.IGNORECASE):
                return True
        return False
