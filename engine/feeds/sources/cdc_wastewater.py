"""CDC — detección de patógenos en aguas residuales."""

from __future__ import annotations

from typing import Any, ClassVar

from engine.feeds.normalizer import NormalizedEvent, clamp, parse_timestamp
from engine.feeds.sources.base import FeedSource


class CDCWastewater(FeedSource):
    """Monitorea detección de patógenos en sistemas de aguas residuales."""

    name: ClassVar[str] = "CDC-Wastewater"
    domain: ClassVar[str] = "health"
    event_type: ClassVar[str] = "pathogen_signal"
    endpoint: ClassVar[str] = "https://data.cdc.gov/resource/g653-rqe2.json?$limit=20"

    def parse(self, payload: Any) -> list[NormalizedEvent]:
        """Extrae señales de patógenos detectados en aguas residuales."""
        if not isinstance(payload, list):
            return []

        events = []
        for record in payload:
            if not isinstance(record, dict):
                continue

            site = record.get("wwtp_name", "").strip()
            pathogen = record.get("pathogen", "").strip()

            if not site or not pathogen:
                continue

            # Extraer nivel de detección (normalizado a 0-1)
            level = record.get("detection_level")
            try:
                level = float(level) if level is not None else 0.5
            except (ValueError, TypeError):
                level = 0.5

            # Salience basada en intensidad de detección
            salience = clamp(0.3 + (level * 0.7))

            # Timestamp si está disponible
            date_collect = record.get("date_collected")
            if date_collect:
                date_collect = parse_timestamp(date_collect)

            external_id = f"{site}_{pathogen}".lower().replace(" ", "_")

            events.append(
                NormalizedEvent(
                    source=self.name,
                    event_type=self.event_type,
                    title=f"{pathogen} detected at {site}",
                    description=f"Wastewater pathogen detection: {level:.2f}",
                    magnitude=level,
                    salience=salience,
                    event_time=date_collect,
                    external_id=external_id,
                    raw={
                        "site": site,
                        "pathogen": pathogen,
                        "detection_level": round(level, 3),
                    },
                )
            )

        return events
