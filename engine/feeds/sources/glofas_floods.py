"""GloFAS — sistema global de alerta temprana de inundaciones."""

from __future__ import annotations

from typing import Any, ClassVar

from engine.feeds.normalizer import NormalizedEvent, clamp, parse_timestamp
from engine.feeds.sources.base import FeedSource


class GloFASFloods(FeedSource):
    """Monitorea alertas de inundación de GloFAS Copernicus."""

    name: ClassVar[str] = "GloFAS"
    domain: ClassVar[str] = "disasters"
    event_type: ClassVar[str] = "flood_alert"
    endpoint: ClassVar[str] = "https://global-flood.emergency.copernicus.eu/api/v2/floods/"

    def parse(self, payload: Any) -> list[NormalizedEvent]:
        """Extrae eventos de inundación del API de GloFAS."""
        if not isinstance(payload, dict):
            return []

        floods = payload.get("features", [])
        if not isinstance(floods, list):
            return []

        events = []
        for flood_entry in floods:
            if not isinstance(flood_entry, dict):
                continue

            properties = flood_entry.get("properties", {})
            if not isinstance(properties, dict):
                continue

            location = properties.get("glofas_location", "").strip()
            country = properties.get("country", "").strip()
            if not (location or country):
                continue

            risk_level = properties.get("flood_risk", "").upper()
            risk_level_map = {
                "MINIMAL": 0.2,
                "LOW": 0.4,
                "MODERATE": 0.6,
                "HIGH": 0.85,
                "EXTREME": 1.0,
            }
            salience = risk_level_map.get(risk_level, 0.5)

            affected_population = properties.get("population_affected", 0)
            if affected_population:
                salience = clamp(salience + (min(affected_population / 1000000, 0.3)))

            # Extraer coordenadas si están disponibles
            geometry = flood_entry.get("geometry", {})
            coords = geometry.get("coordinates", [])
            lon = lat = None
            if isinstance(coords, list) and len(coords) >= 2:
                try:
                    lon = float(coords[0])
                    lat = float(coords[1])
                except (ValueError, TypeError):
                    pass

            pub_date = properties.get("forecast_date")
            if pub_date:
                pub_date = parse_timestamp(pub_date)

            title = f"{location or country} — {risk_level}"
            external_id = f"glofas_{(location or country).lower().replace(' ', '_')}"

            events.append(
                NormalizedEvent(
                    source=self.name,
                    event_type=self.event_type,
                    title=title,
                    description=f"Riesgo de inundación: {affected_population} personas potencialmente afectadas"
                    if affected_population
                    else "Alerta de inundación",
                    magnitude=float(affected_population) if affected_population else 0.0,
                    salience=clamp(salience),
                    latitude=lat,
                    longitude=lon,
                    event_time=pub_date,
                    external_id=external_id,
                    raw={
                        "location": location,
                        "country": country,
                        "risk_level": risk_level,
                        "population_affected": affected_population,
                    },
                )
            )

        return events
