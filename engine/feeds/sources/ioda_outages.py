"""IODA — detección de cortes de conectividad a internet por país."""

from __future__ import annotations

from typing import Any, ClassVar

from engine.feeds.normalizer import NormalizedEvent, clamp, parse_timestamp
from engine.feeds.sources.base import FeedSource


class IODAOutages(FeedSource):
    """Monitorea cortes y anomalías de conectividad global."""

    name: ClassVar[str] = "IODA"
    domain: ClassVar[str] = "infrastructure"
    event_type: ClassVar[str] = "outage"
    endpoint: ClassVar[str] = "https://api.ioda.inetintel.cc.gatech.edu/v2/outages?status=ongoing"

    def parse(self, payload: Any) -> list[NormalizedEvent]:
        """Extrae eventos de corte de la API IODA."""
        if not isinstance(payload, dict):
            return []

        outages = payload.get("data", {}).get("outages", [])
        if not isinstance(outages, list):
            return []

        events = []
        for outage in outages:
            if not isinstance(outage, dict):
                continue

            entity_data = outage.get("entity", {})
            if not isinstance(entity_data, dict):
                continue

            entity_type = entity_data.get("type", "").lower()
            entity_name = entity_data.get("name", "").strip()
            if not entity_name:
                continue

            # Extraer fechas y duración
            start_time = outage.get("start_time")
            if start_time:
                start_time = parse_timestamp(start_time)

            end_time = outage.get("end_time")
            if end_time:
                end_time = parse_timestamp(end_time)

            # Calcular salience basado en duración y localización
            duration_minutes = outage.get("duration", 0)
            salience = 0.3 + min(duration_minutes / 1440, 0.6)  # máx 24h = salience 0.9
            salience = clamp(salience)

            external_id = f"ioda_{entity_type}_{entity_name.lower().replace(' ', '_')}"

            events.append(
                NormalizedEvent(
                    source=self.name,
                    event_type=self.event_type,
                    title=f"{entity_name} ({entity_type})",
                    description=f"Outage detectado por {duration_minutes} minutos"
                    if duration_minutes > 0
                    else "Outage en progreso",
                    magnitude=float(duration_minutes),
                    salience=salience,
                    event_time=start_time,
                    external_id=external_id,
                    raw={
                        "entity_type": entity_type,
                        "entity_name": entity_name,
                        "duration_minutes": duration_minutes,
                    },
                )
            )

        return events
