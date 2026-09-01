"""GDELT — cobertura mediática global de crisis.

Advertencia operativa: la API pública de GDELT limita peticiones con dureza y
las consultas por `theme:` suelen agotar el tiempo de espera. Se usa una
consulta por palabras clave, que responde con fiabilidad razonable, y se cuenta
con que la fuente falle de vez en cuando: el ingestor lo absorbe.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, ClassVar

from engine.feeds.normalizer import NormalizedEvent, clamp
from engine.feeds.sources.base import FeedSource

# Palabras que elevan la relevancia de un titular.
ESCALATION_TERMS = (
    "airstrike",
    "invasion",
    "casualties",
    "killed",
    "emergency",
    "evacuat",
    "sanction",
    "coup",
    "explosion",
    "missile",
)
DEESCALATION_TERMS = ("ceasefire", "truce", "agreement", "peace talks", "withdrawal")


class GDELT(FeedSource):
    """Titulares recientes sobre conflicto, sanciones y crisis."""

    name: ClassVar[str] = "GDELT"
    domain: ClassVar[str] = "geopolitical"
    event_type: ClassVar[str] = "media_signal"
    endpoint: ClassVar[str] = (
        "https://api.gdeltproject.org/api/v2/doc/doc"
        "?query=(sanctions%20OR%20airstrike%20OR%20ceasefire%20OR%20evacuation)"
        "%20sourcelang:english"
        "&mode=ArtList&format=json&maxrecords=50&timespan=1d&sort=DateDesc"
    )

    def parse(self, payload: Any) -> list[NormalizedEvent]:
        events = []
        for article in payload.get("articles", []):
            title = article.get("title") or ""
            if not title.strip():
                continue

            events.append(
                NormalizedEvent(
                    source=self.name,
                    event_type=self.event_type,
                    title=title,
                    description=f"{article.get('domain')} ({article.get('sourcecountry')})",
                    url=article.get("url"),
                    salience=self._salience(title),
                    event_time=self._seendate(article.get("seendate")),
                    external_id=article.get("url"),
                    raw={
                        "domain": article.get("domain"),
                        "sourcecountry": article.get("sourcecountry"),
                    },
                )
            )
        return events

    @staticmethod
    def _seendate(value: str | None) -> datetime | None:
        """GDELT usa su propio formato: `20260901T050000Z`."""
        if not value:
            return None
        try:
            return datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)
        except ValueError:
            return None

    @staticmethod
    def _salience(title: str) -> float:
        """Heurística léxica: sin el enriquecimiento GKG no hay tono disponible."""
        lowered = title.lower()
        score = 0.45
        score += 0.12 * sum(term in lowered for term in ESCALATION_TERMS)
        score -= 0.08 * sum(term in lowered for term in DEESCALATION_TERMS)
        return clamp(score)
