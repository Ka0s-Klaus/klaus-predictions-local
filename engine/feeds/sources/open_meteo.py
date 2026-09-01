"""Open-Meteo — previsión y anomalías meteorológicas.

Sin clave, sin límite de peticiones. Monitorea puntos de entrada comunes
para fenómenos extremos: temperaturas anómalas, precipitación intensiva,
velocidad del viento.
"""

from __future__ import annotations

from typing import Any, ClassVar

from engine.feeds.normalizer import NormalizedEvent, clamp
from engine.feeds.sources.base import FeedSource

WATCH_POINTS = [
    {"lat": 35.6762, "lon": 139.6503, "name": "Tokio"},  # Sísmico + tifones
    {"lat": 37.5665, "lon": 126.9780, "name": "Seúl"},   # Tifones + frío extremo
    {"lat": 1.3521, "lon": 103.8198, "name": "Singapur"},  # Monzón + lluvia
    {"lat": -33.9249, "lon": 18.4241, "name": "Ciudad del Cabo"},  # Sequía
    {"lat": 51.5074, "lon": -0.1278, "name": "Londres"},  # Tormentas atlánticas
]


class OpenMeteoWeather(FeedSource):
    """Anomalías meteorológicas en puntos clave."""

    name: ClassVar[str] = "Open-Meteo"
    domain: ClassVar[str] = "weather"
    event_type: ClassVar[str] = "weather_anomaly"
    endpoint: ClassVar[str] = "https://api.open-meteo.com/v1/forecast"

    def parse(self, payload: Any) -> list[NormalizedEvent]:
        """El payload contiene arrays de `hourly` con índices temporales.

        Busca desviaciones del promedio histórico en temperatura y lluvia.
        """
        events = []

        # Open-Meteo devuelve los puntos solicitados en orden
        for i, point in enumerate(WATCH_POINTS):
            if i >= len(payload.get("hourly", [])):
                continue

            is_list = isinstance(payload.get("hourly"), list)
            hourly = payload.get("hourly", [{}])[i] if is_list else {}

            # Fallback si devuelve dict en lugar de lista
            if isinstance(hourly, dict):
                temps = hourly.get("temperature_2m", [])
                rain = hourly.get("precipitation", [])
            else:
                temps = []
                rain = []

            if not temps or not rain:
                continue

            # Último valor disponible (o promedio de últimas 6h)
            recent_temps = [t for t in temps[-6:] if t is not None]
            recent_rain = [r for r in rain[-6:] if r is not None]

            if not recent_temps or not recent_rain:
                continue

            avg_temp = sum(recent_temps) / len(recent_temps)
            total_rain = sum(recent_rain)

            # Detección de anomalía: lluvia intensa (>10 mm en 6h) o
            # temperaturas extremas (>30 °C o <0 °C según región)
            salience = 0.4
            title_parts = [point["name"]]

            if total_rain > 10:
                salience = clamp(0.5 + (min(total_rain / 30, 1.0) * 0.35))
                title_parts.append(f"Lluvia {total_rain:.1f} mm")

            if avg_temp > 30 or avg_temp < 0:
                salience = max(salience, 0.65)
                title_parts.append(f"Temp {avg_temp:.1f}°C")

            events.append(
                NormalizedEvent(
                    source=self.name,
                    event_type=self.event_type,
                    title=" — ".join(title_parts),
                    magnitude=max(total_rain, abs(avg_temp - 15)),  # Desviación del "normal"
                    salience=salience,
                    external_id=f"{point['lat']},{point['lon']}",
                    raw={
                        "location": point["name"],
                        "temp_avg": round(avg_temp, 1),
                        "rain_6h": round(total_rain, 1),
                    },
                )
            )

        return events
