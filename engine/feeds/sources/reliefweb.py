"""ReliefWeb — situaciones de crisis humanitaria.

API sin clave, bien documentada y con actualizaciones frecuentes de
situaciones de desplazamiento, hambre y acceso a servicios en conflictos
y desastres naturales.
"""

from __future__ import annotations

from typing import Any, ClassVar

from engine.feeds.normalizer import NormalizedEvent, parse_timestamp
from engine.feeds.sources.base import FeedSource


class ReliefWebSituations(FeedSource):
    """Crisis humanitarias de ReliefWeb."""

    name: ClassVar[str] = "ReliefWeb"
    domain: ClassVar[str] = "humanitarian"
    event_type: ClassVar[str] = "humanitarian_crisis"
    endpoint: ClassVar[str] = (
        "https://api.reliefweb.int/v1/reports?"
        "appname=pythia&limit=100&"
        "filter[field]=report_type&filter[operator]==&filter[value]=Situation Report"
    )

    def parse(self, payload: Any) -> list[NormalizedEvent]:
        """El payload es {'data': [...]}."""
        events = []
        data = payload.get("data", [])

        for report in data:
            fields = report.get("fields", {})
            title = fields.get("title", "")
            if not title:
                continue

            primary_country = fields.get("primary_country", [])
            disaster = fields.get("disaster", [])
            date = fields.get("date", {}).get("original", "")

            # Salience según severidad — si hay múltiples países o desastres,
            # es una situación más grave.
            country_count = len(primary_country) if primary_country else 0
            disaster_count = len(disaster) if disaster else 0
            severity = min(0.3 + (country_count + disaster_count) * 0.1, 0.95)

            events.append(
                NormalizedEvent(
                    source=self.name,
                    event_type=self.event_type,
                    title=title[:80],
                    magnitude=float(country_count + disaster_count),
                    salience=severity,
                    external_id=report.get("id", ""),
                    event_time=parse_timestamp(date),
                    raw={
                        "title": title,
                        "countries": primary_country[:3],
                        "disasters": disaster[:3],
                    },
                )
            )

        return events
