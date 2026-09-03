"""OpenSky — actividad de vuelos comerciales en tiempo real."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, ClassVar

from engine.feeds.normalizer import NormalizedEvent, clamp, parse_timestamp
from engine.feeds.sources.base import FeedSource


class OpenSkyFlights(FeedSource):
    """Monitorea actividad de vuelos y congestión aérea."""

    name: ClassVar[str] = "Flights"
    domain: ClassVar[str] = "logistics"
    event_type: ClassVar[str] = "flight_activity"
    endpoint: ClassVar[str] = "https://opensky-network.org/api/states/all?lamin=25&lamax=72&lomin=-25&lomax=45"

    def parse(self, payload: Any) -> list[NormalizedEvent]:
        """Extrae datos de actividad de vuelos de la API OpenSky."""
        if not isinstance(payload, dict):
            return []

        states = payload.get("states", [])
        if not isinstance(states, list):
            return []

        # Contar aeronaves activas
        active_count = 0
        for state in states:
            if isinstance(state, list) and len(state) > 0:
                active_count += 1

        if active_count == 0:
            return []

        # Crear un único evento por consulta con el conteo total
        timestamp = datetime.now(tz=UTC)
        external_id = f"flights_{int(timestamp.timestamp())}"

        event = NormalizedEvent(
            source=self.name,
            event_type=self.event_type,
            title=f"Active flights in region: {active_count}",
            description=f"Currently tracking {active_count} aircraft in surveillance region",
            magnitude=float(active_count),
            salience=0.4,
            event_time=timestamp,
            external_id=external_id,
            raw={
                "aircraft_count": active_count,
                "region": "Europe/Middle East",
            },
        )

        return [event]
