"""USGS — terremotos significativos de las últimas 24 horas."""

from __future__ import annotations

from typing import Any, ClassVar

from engine.feeds.normalizer import NormalizedEvent, clamp, parse_timestamp
from engine.feeds.sources.base import FeedSource

# Por debajo de M4.5 el ruido sísmico global es constante y no aporta señal.
MIN_MAGNITUDE = 4.5
# Un M8 satura la escala de relevancia.
SATURATION_MAGNITUDE = 8.0


class USGSEarthquakes(FeedSource):
    """GeoJSON de sismos M4.5+ de la última jornada."""

    name: ClassVar[str] = "USGS"
    domain: ClassVar[str] = "disasters"
    event_type: ClassVar[str] = "earthquake"
    endpoint: ClassVar[str] = (
        "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_day.geojson"
    )

    def parse(self, payload: Any) -> list[NormalizedEvent]:
        events = []
        for feature in payload.get("features", []):
            props = feature.get("properties") or {}
            magnitude = props.get("mag")
            if magnitude is None or magnitude < MIN_MAGNITUDE:
                continue

            coords = (feature.get("geometry") or {}).get("coordinates") or []
            longitude = coords[0] if len(coords) > 0 else None
            latitude = coords[1] if len(coords) > 1 else None
            depth_km = coords[2] if len(coords) > 2 else None

            events.append(
                NormalizedEvent(
                    source=self.name,
                    event_type=self.event_type,
                    title=props.get("title") or f"M {magnitude}",
                    description=props.get("place"),
                    url=props.get("url"),
                    latitude=latitude,
                    longitude=longitude,
                    magnitude=magnitude,
                    salience=self._salience(magnitude, props.get("tsunami"), depth_km),
                    event_time=parse_timestamp(props.get("time")),
                    external_id=feature.get("id"),
                    raw={"place": props.get("place"), "depth_km": depth_km},
                )
            )
        return events

    @staticmethod
    def _salience(magnitude: float, tsunami: int | None, depth_km: float | None) -> float:
        """La magnitud manda, pero un sismo somero hace mucho más daño."""
        score = clamp((magnitude - MIN_MAGNITUDE) / (SATURATION_MAGNITUDE - MIN_MAGNITUDE))
        if tsunami:
            score += 0.2
        if depth_km is not None and depth_km < 70:
            score += 0.1
        return clamp(score)
