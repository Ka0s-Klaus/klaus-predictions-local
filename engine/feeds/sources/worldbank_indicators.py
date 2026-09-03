"""WorldBank — indicadores económicos de crecimiento del PIB."""

from __future__ import annotations

from typing import Any, ClassVar

from engine.feeds.normalizer import NormalizedEvent, clamp, parse_timestamp
from engine.feeds.sources.base import FeedSource


class WorldBankIndicators(FeedSource):
    """Monitorea indicadores económicos del Banco Mundial."""

    name: ClassVar[str] = "WorldBank"
    domain: ClassVar[str] = "macro"
    event_type: ClassVar[str] = "economic_indicator"
    endpoint: ClassVar[str] = (
        "https://api.worldbank.org/v2/country/all/indicator/NY.GDP.MKTP.KD.ZG?format=json&mrv=5"
    )

    def parse(self, payload: Any) -> list[NormalizedEvent]:
        """Extrae indicadores económicos del Banco Mundial."""
        if not isinstance(payload, list) or len(payload) < 2:
            return []

        # El primer elemento contiene metadatos, el segundo los datos
        data = payload[1]
        if not isinstance(data, list):
            return []

        events = []
        for indicator in data:
            if not isinstance(indicator, dict):
                continue

            country_code = indicator.get("countryid", "").strip()
            country_name = indicator.get("country", {})
            if isinstance(country_name, dict):
                country_name = country_name.get("value", "").strip()

            if not country_code or not country_name:
                continue

            # Obtener el valor más reciente
            value = indicator.get("value")
            if value is None or value == "":
                continue

            try:
                value = float(value)
            except (ValueError, TypeError):
                continue

            # Salience basada en el signo del cambio (positivo = 0.6, negativo = 0.7)
            salience = 0.6 if value >= 0 else 0.7

            external_id = country_code

            events.append(
                NormalizedEvent(
                    source=self.name,
                    event_type=self.event_type,
                    title=f"{country_name} — GDP Growth",
                    description=f"GDP growth indicator: {value:+.2f}%",
                    magnitude=abs(value),
                    salience=salience,
                    event_time=None,
                    external_id=external_id,
                    raw={
                        "country_code": country_code,
                        "country_name": country_name,
                        "value": round(value, 2),
                    },
                )
            )

        return events
