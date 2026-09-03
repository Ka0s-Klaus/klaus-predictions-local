"""UNHCR — desplazamientos forzados de población."""

from __future__ import annotations

from typing import Any, ClassVar

from engine.feeds.normalizer import NormalizedEvent, clamp, parse_timestamp
from engine.feeds.sources.base import FeedSource


class UNHCRDisplacement(FeedSource):
    """Monitorea desplazamientos y situaciones humanitarias globales."""

    name: ClassVar[str] = "UNHCR"
    domain: ClassVar[str] = "humanitarian"
    event_type: ClassVar[str] = "displacement"
    endpoint: ClassVar[str] = "https://api.unhcr.org/population/v1/population/?limit=20"

    def parse(self, payload: Any) -> list[NormalizedEvent]:
        """Extrae datos de desplazamiento de la API UNHCR."""
        if not isinstance(payload, dict):
            return []

        data = payload.get("data", [])
        if not isinstance(data, list):
            return []

        events = []
        for record in data:
            if not isinstance(record, dict):
                continue

            location = record.get("location", "").strip()
            if not location:
                continue

            # Extraer números de desplazados (refugiados es el principal)
            refugees = record.get("refugees", 0)
            if refugees is None:
                refugees = 0
            try:
                refugees = int(refugees)
            except (ValueError, TypeError):
                refugees = 0

            # Magnitud y salience basados en número de desplazados
            if refugees > 0:
                salience = clamp(0.4 + min(refugees / 100000.0, 0.6))
            else:
                salience = 0.3

            external_id = f"{location}_{refugees}".lower().replace(" ", "_")

            events.append(
                NormalizedEvent(
                    source=self.name,
                    event_type=self.event_type,
                    title=f"{location} — Displacement Crisis",
                    description=f"Refugees and displaced persons: {refugees:,}",
                    magnitude=float(refugees),
                    salience=salience,
                    event_time=None,
                    external_id=external_id,
                    raw={
                        "location": location,
                        "refugees": refugees,
                        "year": record.get("year"),
                    },
                )
            )

        return events
