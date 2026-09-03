"""USGS Volcano — niveles de alerta de volcanes estadounidenses."""

from __future__ import annotations

from typing import Any, ClassVar

from engine.feeds.normalizer import NormalizedEvent, clamp, parse_timestamp
from engine.feeds.sources.base import FeedSource


class USGSVolcano(FeedSource):
    """Monitorea niveles de alerta de volcanes en tiempo real."""

    name: ClassVar[str] = "USGS-Volcano"
    domain: ClassVar[str] = "disasters"
    event_type: ClassVar[str] = "volcano_alert"
    endpoint: ClassVar[str] = "https://volcanoes.usgs.gov/vsc/api/volcanoApi/elevated"

    def parse(self, payload: Any) -> list[NormalizedEvent]:
        """Extrae volcanes activos de la API USGS."""
        if not isinstance(payload, dict):
            return []

        volcanoes = payload.get("volcano", [])
        if not isinstance(volcanoes, list):
            return []

        events = []
        alert_level_map = {
            "NORMAL": 0.3,
            "ADVISORY": 0.55,
            "WARNING": 0.85,
            "CRITICAL": 1.0,
        }

        for vol in volcanoes:
            if not isinstance(vol, dict):
                continue

            name = vol.get("name", "").strip()
            if not name:
                continue

            alert_level = vol.get("level", "").upper()
            salience = alert_level_map.get(alert_level, 0.4)

            # Información de crisis si está disponible
            crisis_level = vol.get("crisis_level", "")
            if crisis_level and crisis_level.upper() != "NORMAL":
                salience = clamp(salience + 0.15)

            lat = vol.get("latitude")
            lon = vol.get("longitude")
            if lat is not None and lon is not None:
                try:
                    lat = float(lat)
                    lon = float(lon)
                except (ValueError, TypeError):
                    lat = lon = None

            event_time = vol.get("last_update_utc")
            if event_time:
                event_time = parse_timestamp(event_time)

            external_id = f"usgs_vol_{vol.get('volcano_id', name).lower()}"

            events.append(
                NormalizedEvent(
                    source=self.name,
                    event_type=self.event_type,
                    title=f"{name} — {alert_level}",
                    description=crisis_level if crisis_level else "Sin cambios en estado de alerta",
                    magnitude=float(list(alert_level_map.values()).index(salience))
                    if salience in alert_level_map.values()
                    else 1.0,
                    salience=salience,
                    latitude=lat,
                    longitude=lon,
                    event_time=event_time,
                    external_id=external_id,
                    raw={
                        "volcano_id": vol.get("volcano_id"),
                        "alert_level": alert_level,
                        "crisis_level": crisis_level,
                    },
                )
            )

        return events
