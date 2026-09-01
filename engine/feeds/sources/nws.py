"""NWS — avisos meteorológicos activos en Estados Unidos."""

from __future__ import annotations

from typing import Any, ClassVar

from engine.feeds.normalizer import NormalizedEvent, clamp, parse_timestamp
from engine.feeds.sources.base import FeedSource

SEVERITY_SALIENCE: dict[str, float] = {
    "Extreme": 0.95,
    "Severe": 0.75,
    "Moderate": 0.50,
    "Minor": 0.30,
    "Unknown": 0.40,
}
URGENCY_BONUS: dict[str, float] = {"Immediate": 0.10, "Expected": 0.05}


class NWSAlerts(FeedSource):
    """Avisos activos del National Weather Service.

    El endpoint no admite `limit`: devuelve 400. Se acota por severidad, que
    además es lo único que interesa aquí.
    """

    name: ClassVar[str] = "NWS"
    domain: ClassVar[str] = "weather"
    event_type: ClassVar[str] = "weather_alert"
    endpoint: ClassVar[str] = "https://api.weather.gov/alerts/active?severity=Extreme,Severe"
    headers: ClassVar[dict[str, str]] = {"Accept": "application/geo+json"}

    def parse(self, payload: Any) -> list[NormalizedEvent]:
        events = []
        for feature in payload.get("features", []):
            props = feature.get("properties") or {}
            severity = props.get("severity", "Unknown")

            events.append(
                NormalizedEvent(
                    source=self.name,
                    event_type=props.get("event") or self.event_type,
                    title=props.get("headline") or props.get("event") or "(aviso NWS)",
                    description=props.get("description"),
                    url=props.get("@id") or props.get("id"),
                    salience=clamp(
                        SEVERITY_SALIENCE.get(severity, 0.4)
                        + URGENCY_BONUS.get(props.get("urgency", ""), 0.0)
                    ),
                    event_time=parse_timestamp(props.get("onset") or props.get("sent")),
                    external_id=props.get("id") or feature.get("id"),
                    raw={
                        "severity": severity,
                        "urgency": props.get("urgency"),
                        "areaDesc": props.get("areaDesc"),
                    },
                )
            )
        return events
