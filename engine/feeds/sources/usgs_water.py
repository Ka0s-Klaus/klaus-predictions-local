"""USGS — monitoreo de niveles de agua y caudal de ríos."""

from __future__ import annotations

from typing import Any, ClassVar

from engine.feeds.normalizer import NormalizedEvent, clamp, parse_timestamp
from engine.feeds.sources.base import FeedSource


class USGSWater(FeedSource):
    """Monitorea niveles de agua en sitios de medición USGS."""

    name: ClassVar[str] = "USGS-Water"
    domain: ClassVar[str] = "disasters"
    event_type: ClassVar[str] = "water_level"
    endpoint: ClassVar[str] = (
        "https://api.waterdata.usgs.gov/ogcapi/v0/collections/monitoring-locations/items?limit=100"
    )

    def parse(self, payload: Any) -> list[NormalizedEvent]:
        """Extrae datos de niveles de agua de la API USGS (OGC API v0 format)."""
        if not isinstance(payload, dict):
            return []

        features = payload.get("features", [])
        if not isinstance(features, list):
            return []

        events = []
        for feature in features:
            if not isinstance(feature, dict):
                continue

            properties = feature.get("properties", {})
            if not isinstance(properties, dict):
                continue

            site_name = properties.get("name", "").strip()
            if not site_name:
                site_name = properties.get("monitoringLocationNumber", "").strip()

            if not site_name:
                continue

            # Extraer coordenadas de geometry
            geometry = feature.get("geometry", {})
            coords = geometry.get("coordinates", [])
            lon = lat = None
            if isinstance(coords, list) and len(coords) >= 2:
                try:
                    lon = float(coords[0])
                    lat = float(coords[1])
                except (ValueError, TypeError):
                    pass

            # Usar un valor genérico de magnitud/salience
            # (la nueva API no proporciona datos en tiempo real de caudal en este endpoint)
            salience = 0.4
            magnitude = 0.0

            external_id = site_name.lower().replace(" ", "_")

            events.append(
                NormalizedEvent(
                    source=self.name,
                    event_type=self.event_type,
                    title=f"Water Level: {site_name}",
                    description="USGS monitoring location",
                    magnitude=magnitude,
                    salience=salience,
                    latitude=lat if lat and -90 <= lat <= 90 else None,
                    longitude=lon if lon and -180 <= lon <= 180 else None,
                    event_time=None,
                    external_id=external_id,
                    raw={
                        "site_no": site_name,
                    },
                )
            )

        return events
