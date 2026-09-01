"""NOAA SWPC — alertas de clima espacial.

Tormentas geomagnéticas y flujo de partículas: afectan a redes eléctricas,
satélites, GPS y rutas polares de aviación.
"""

from __future__ import annotations

import re
from typing import Any, ClassVar

from engine.feeds.normalizer import NormalizedEvent, parse_timestamp
from engine.feeds.sources.base import FeedSource

# Escalas NOAA: G (geomagnética), S (radiación solar), R (apagón de radio).
# El dígito final es la severidad, de 1 a 5.
_SCALE = re.compile(r"\b([GSR])([1-5])\b")

# Los mensajes traen un bloque de cabecera antes del texto útil.
_SKIP_PREFIXES = (
    "Space Weather Message Code:",
    "Serial Number:",
    "Issue Time:",
    "Continuation of Serial Number:",
)


class SWPCAlerts(FeedSource):
    """Alertas, avisos y observaciones del Space Weather Prediction Center."""

    name: ClassVar[str] = "SWPC"
    domain: ClassVar[str] = "space-weather"
    event_type: ClassVar[str] = "space_weather_alert"
    endpoint: ClassVar[str] = "https://services.swpc.noaa.gov/products/alerts.json"

    def parse(self, payload: Any) -> list[NormalizedEvent]:
        events = []
        for item in payload:
            message = item.get("message") or ""
            headline = self._headline(message)
            if not headline:
                continue

            events.append(
                NormalizedEvent(
                    source=self.name,
                    event_type=self.event_type,
                    title=headline,
                    description=message,
                    salience=self._salience(message),
                    event_time=parse_timestamp(item.get("issue_datetime")),
                    external_id=f"{item.get('product_id')}:{item.get('issue_datetime')}",
                    raw={"product_id": item.get("product_id")},
                )
            )
        return events

    @staticmethod
    def _headline(message: str) -> str | None:
        """Primera línea con contenido real, saltándose la cabecera del boletín."""
        for line in message.replace("\r", "").split("\n"):
            line = line.strip()
            if line and not line.startswith(_SKIP_PREFIXES):
                return line
        return None

    @staticmethod
    def _salience(message: str) -> float:
        """La escala NOAA va de 1 a 5; se mapea al tramo 0.4-1.0."""
        matches = _SCALE.findall(message)
        if not matches:
            return 0.4
        worst = max(int(level) for _, level in matches)
        return round(0.4 + (worst - 1) * 0.15, 3)
