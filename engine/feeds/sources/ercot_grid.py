"""ERCOT — niveles de demanda vs capacidad del grid de Texas."""

from __future__ import annotations

from typing import Any, ClassVar

from engine.feeds.normalizer import NormalizedEvent, clamp, parse_timestamp
from engine.feeds.sources.base import FeedSource


class ERCOTGrid(FeedSource):
    """Monitorea estrés y congestión del grid eléctrico de Texas."""

    name: ClassVar[str] = "ERCOT"
    domain: ClassVar[str] = "energy"
    event_type: ClassVar[str] = "grid_stress"
    endpoint: ClassVar[str] = "https://www.ercot.com/api/1/services/read/dashboards/daily-prc.json"

    def parse(self, payload: Any) -> list[NormalizedEvent]:
        """Extrae datos de estrés del grid de ERCOT."""
        if not isinstance(payload, dict):
            return []

        # Buscar datos de demanda vs capacidad
        data = payload.get("data", [])
        if not isinstance(data, list):
            return []

        events = []
        for record in data:
            if not isinstance(record, dict):
                continue

            # Extraer demanda y capacidad
            demand = record.get("demand")
            capacity = record.get("capacity")
            timestamp = record.get("timestamp")

            if demand is None or capacity is None:
                continue

            try:
                demand = float(demand)
                capacity = float(capacity)
            except (ValueError, TypeError):
                continue

            if capacity == 0:
                continue

            # Calcular ratio de estrés
            stress_ratio = demand / capacity
            salience = clamp(0.4 + (stress_ratio - 0.5) * 1.2)

            if timestamp:
                event_time = parse_timestamp(timestamp)
            else:
                event_time = None

            external_id = (
                f"ercot_{int(timestamp) if isinstance(timestamp, (int, float)) else 'current'}"
            )

            events.append(
                NormalizedEvent(
                    source=self.name,
                    event_type=self.event_type,
                    title=f"Grid Stress: {stress_ratio:.1%}",
                    description=f"Demand: {demand:.0f}MW / Capacity: {capacity:.0f}MW",
                    magnitude=stress_ratio,
                    salience=salience,
                    event_time=event_time,
                    external_id=external_id,
                    raw={
                        "demand_mw": round(demand, 0),
                        "capacity_mw": round(capacity, 0),
                        "stress_ratio": round(stress_ratio, 3),
                    },
                )
            )

        return events
