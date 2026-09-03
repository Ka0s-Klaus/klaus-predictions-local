"""UCDP — eventos de conflicto con víctimas y localizaciones."""

from __future__ import annotations

from typing import Any, ClassVar

from engine.feeds.normalizer import NormalizedEvent, clamp, parse_timestamp
from engine.feeds.sources.base import FeedSource


class UCDPConflicts(FeedSource):
    """Monitorea eventos de conflictos geopolíticos documentados."""

    name: ClassVar[str] = "UCDP"
    domain: ClassVar[str] = "conflict"
    event_type: ClassVar[str] = "conflict"
    endpoint: ClassVar[str] = "https://ucdpapi.pcr.uu.se/api/gedevents/23.1?pagesize=20"

    def parse(self, payload: Any) -> list[NormalizedEvent]:
        """Extrae eventos de conflicto de la API UCDP."""
        if not isinstance(payload, dict):
            return []

        result_data = payload.get("result", {})
        if not isinstance(result_data, dict):
            return []

        events_data = result_data.get("data", [])
        if not isinstance(events_data, list):
            return []

        events = []
        for event in events_data:
            if not isinstance(event, dict):
                continue

            event_id = event.get("event_id_cnty")
            if not event_id:
                continue

            year = event.get("year")
            month = event.get("month")
            day = event.get("day")

            # Construir timestamp si está disponible
            event_time = None
            if year and month and day:
                try:
                    from datetime import datetime, UTC
                    event_time = datetime(year, month, day, tzinfo=UTC)
                except (ValueError, TypeError):
                    pass

            # Extraer información de víctimas y magnitud
            deaths = event.get("deaths_a", 0) + event.get("deaths_b", 0) + event.get(
                "deaths_civilians", 0
            )
            deaths = int(deaths) if isinstance(deaths, (int, float)) else 0

            # Salience basada en número de muertes
            salience = clamp(0.3 + min(deaths / 100.0, 0.7))

            country = event.get("country", "").strip()
            if not country:
                country = "Unknown"

            side_a = event.get("side_a", "").strip()
            side_b = event.get("side_b", "").strip()

            title_parts = [country]
            if side_a and side_b:
                title_parts.append(f"{side_a} vs {side_b}")
            elif side_a:
                title_parts.append(f"{side_a}")

            title = " — ".join(title_parts) if len(title_parts) > 1 else country

            external_id = str(event_id)

            events.append(
                NormalizedEvent(
                    source=self.name,
                    event_type=self.event_type,
                    title=title,
                    description=f"Conflict event with {deaths} deaths reported",
                    magnitude=float(deaths),
                    salience=salience,
                    event_time=event_time,
                    external_id=external_id,
                    raw={
                        "event_id_cnty": event_id,
                        "country": country,
                        "deaths": deaths,
                        "side_a": side_a,
                    },
                )
            )

        return events
