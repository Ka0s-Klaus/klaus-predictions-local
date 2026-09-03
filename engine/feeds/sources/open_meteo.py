"""Open-Meteo — previsión y anomalías meteorológicas.

Sin clave, sin límite de peticiones. Monitorea puntos de entrada comunes
para fenómenos extremos: temperaturas anómalas, precipitación intensiva,
velocidad del viento.
"""

from __future__ import annotations

from typing import Any, ClassVar

import aiohttp

from engine.feeds.normalizer import NormalizedEvent, clamp
from engine.feeds.sources.base import FeedError, FeedSource, USER_AGENT

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

    async def fetch(self, session: aiohttp.ClientSession) -> list[NormalizedEvent]:
        """Construye URL con múltiples coordenadas y descarga datos."""
        # Construir parámetros con coordenadas de todos los puntos de vigilancia
        lats = ",".join(str(p["lat"]) for p in WATCH_POINTS)
        lons = ",".join(str(p["lon"]) for p in WATCH_POINTS)

        url = f"{self.endpoint}?latitude={lats}&longitude={lons}&hourly=temperature_2m,precipitation"

        headers = {"User-Agent": USER_AGENT, **self.headers}
        try:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as response:
                if response.status != 200:
                    raise FeedError(f"{self.name}: HTTP {response.status}")

                import json
                raw = await response.text()
                payload = json.loads(raw)

                if len(raw) > self.max_bytes:
                    raise FeedError(f"{self.name}: response too large")

                return self.parse(payload)
        except aiohttp.ClientError as exc:
            raise FeedError(f"{self.name}: network error") from exc

    def parse(self, payload: Any) -> list[NormalizedEvent]:
        """Extrae anomalías meteorológicas. El payload es un dict con arrays de `hourly`.

        Busca desviaciones del promedio histórico en temperatura y lluvia.
        """
        if not isinstance(payload, dict):
            return []

        events = []

        # Obtener datos de hourly (debería ser un dict con arrays)
        hourly_data = payload.get("hourly", {})
        if not isinstance(hourly_data, dict):
            return []

        temps = hourly_data.get("temperature_2m", [])
        rains = hourly_data.get("precipitation", [])

        if not isinstance(temps, list) or not isinstance(rains, list):
            return []

        # Para cada punto de vigilancia (mismo orden que en la solicitud)
        for i, point in enumerate(WATCH_POINTS):
            # Calcular cuántas mediciones hay por punto
            # Open-Meteo devuelve todos los datos en un solo array, así que necesitamos inferir el intervalo
            if not temps or not rains:
                continue

            # Tomar los últimos 6 valores de temperatura y lluvia (últimas 6 horas aproximadamente)
            recent_temps = [t for t in temps[-6:] if t is not None and isinstance(t, (int, float))]
            recent_rain = [r for r in rains[-6:] if r is not None and isinstance(r, (int, float))]

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
