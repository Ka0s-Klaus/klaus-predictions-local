"""NHC — ciclones tropicales activos."""

from __future__ import annotations

from typing import Any, ClassVar

from engine.feeds.normalizer import NormalizedEvent, clamp, parse_timestamp
from engine.feeds.sources.base import FeedSource

# Escala Saffir-Simpson aproximada a partir de la clasificación del NHC.
CLASSIFICATION_SALIENCE: dict[str, float] = {
    "HU": 0.85,  # Huracán
    "MH": 0.95,  # Huracán mayor
    "TS": 0.65,  # Tormenta tropical
    "TD": 0.45,  # Depresión tropical
    "PTC": 0.40,  # Ciclón potencial
    "STS": 0.60,
    "SD": 0.40,
}
HURRICANE_THRESHOLD_KT = 64.0


def _to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class NHCStorms(FeedSource):
    """Tormentas activas en las cuencas que vigila el National Hurricane Center."""

    name: ClassVar[str] = "NHC"
    domain: ClassVar[str] = "weather"
    event_type: ClassVar[str] = "tropical_cyclone"
    endpoint: ClassVar[str] = "https://www.nhc.noaa.gov/CurrentStorms.json"

    def parse(self, payload: Any) -> list[NormalizedEvent]:
        events = []
        for storm in payload.get("activeStorms", []):
            classification = (storm.get("classification") or "").upper()
            wind_kt = _to_float(storm.get("intensity"))
            name = storm.get("name") or "(sin nombre)"

            events.append(
                NormalizedEvent(
                    source=self.name,
                    event_type=self.event_type,
                    title=f"{storm.get('tcType') or classification} {name}".strip(),
                    description=(
                        f"Cuenca {storm.get('binNumber')}, "
                        f"vientos {wind_kt or '?'} kt, "
                        f"presión {storm.get('pressure') or '?'} mb"
                    ),
                    url=(storm.get("publicAdvisory") or {}).get("url"),
                    latitude=_to_float(storm.get("latitudeNumeric")),
                    longitude=_to_float(storm.get("longitudeNumeric")),
                    magnitude=wind_kt,
                    salience=self._salience(classification, wind_kt),
                    event_time=parse_timestamp(storm.get("lastUpdate")),
                    external_id=storm.get("id"),
                    raw={"classification": classification, "movement": storm.get("movementDir")},
                )
            )
        return events

    @staticmethod
    def _salience(classification: str, wind_kt: float | None) -> float:
        base = CLASSIFICATION_SALIENCE.get(classification, 0.5)
        if wind_kt is not None and wind_kt >= HURRICANE_THRESHOLD_KT:
            # Cada 20 kt por encima del umbral de huracán suma relevancia.
            base += min(0.15, (wind_kt - HURRICANE_THRESHOLD_KT) / 20 * 0.05)
        return clamp(base)
