"""NASA EONET — eventos naturales abiertos (volcanes, incendios, tormentas)."""

from __future__ import annotations

from typing import Any, ClassVar

from engine.feeds.normalizer import NormalizedEvent, parse_timestamp
from engine.feeds.sources.base import FeedSource

# Relevancia por categoría de EONET. Lo que puede matar gente hoy pesa más.
CATEGORY_SALIENCE: dict[str, float] = {
    "volcanoes": 0.80,
    "severeStorms": 0.75,
    "wildfires": 0.70,
    "floods": 0.70,
    "earthquakes": 0.70,
    "landslides": 0.65,
    "drought": 0.55,
    "dustHaze": 0.45,
    "seaLakeIce": 0.40,
    "snow": 0.40,
    "temperatureExtremes": 0.55,
    "manmade": 0.60,
    "waterColor": 0.30,
}
DEFAULT_SALIENCE = 0.5


class EONET(FeedSource):
    """Agregador de eventos naturales de la NASA."""

    name: ClassVar[str] = "EONET"
    domain: ClassVar[str] = "disasters"
    event_type: ClassVar[str] = "natural_event"
    endpoint: ClassVar[str] = "https://eonet.gsfc.nasa.gov/api/v3/events?status=open&limit=100"

    def parse(self, payload: Any) -> list[NormalizedEvent]:
        events = []
        for item in payload.get("events", []):
            categories = [c.get("id", "") for c in item.get("categories") or []]
            latitude, longitude, when = self._last_position(item.get("geometry") or [])

            events.append(
                NormalizedEvent(
                    source=self.name,
                    event_type=categories[0] if categories else self.event_type,
                    title=item.get("title") or "(evento EONET)",
                    description=item.get("description"),
                    url=item.get("link"),
                    latitude=latitude,
                    longitude=longitude,
                    salience=max(
                        (CATEGORY_SALIENCE.get(c, DEFAULT_SALIENCE) for c in categories),
                        default=DEFAULT_SALIENCE,
                    ),
                    event_time=when,
                    external_id=item.get("id"),
                    raw={"categories": categories},
                )
            )
        return events

    @staticmethod
    def _last_position(geometry: list[dict[str, Any]]) -> tuple[float | None, float | None, Any]:
        """EONET da la traza completa; interesa dónde está el evento ahora."""
        for entry in reversed(geometry):
            coords = entry.get("coordinates")
            when = parse_timestamp(entry.get("date"))
            # Los polígonos (incendios extensos) llegan anidados; se ignoran.
            is_point = isinstance(coords, list) and len(coords) == 2
            if is_point and isinstance(coords[0], (int, float)):
                return coords[1], coords[0], when
            if when is not None:
                return None, None, when
        return None, None, None
