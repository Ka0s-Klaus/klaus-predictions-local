"""Copernicus EMS — activaciones del servicio de gestión de emergencias."""

from __future__ import annotations

from typing import Any, ClassVar

from engine.feeds.normalizer import NormalizedEvent, clamp, parse_timestamp
from engine.feeds.sources.base import FeedSource


class CopernicusEMS(FeedSource):
    """Monitorea activaciones del servicio de gestión de emergencias de Copernicus."""

    name: ClassVar[str] = "Copernicus-EMS"
    domain: ClassVar[str] = "disasters"
    event_type: ClassVar[str] = "emergency_response"
    endpoint: ClassVar[str] = "https://rapidmapping.emergency.copernicus.eu/backend/dashboard-api/public-activations-info/"

    def parse(self, payload: Any) -> list[NormalizedEvent]:
        """Extrae activaciones del API JSON de Copernicus EMS Rapid Mapping."""
        if not isinstance(payload, dict):
            return []

        activations = payload.get("activations", [])
        if not isinstance(activations, list):
            return []

        events = []
        disaster_severity_map = {
            "earthquake": 0.9,
            "flood": 0.75,
            "wildfire": 0.8,
            "storm": 0.7,
            "drought": 0.6,
            "tsunami": 0.95,
            "volcano": 0.85,
        }

        for activation in activations:
            if not isinstance(activation, dict):
                continue

            activation_code = activation.get("activationCode", "").strip()
            activation_name = activation.get("activationName", "").strip()

            if not activation_name:
                continue

            # Extraer fecha de activación
            event_time_str = activation.get("activationTime")
            event_time = parse_timestamp(event_time_str) if event_time_str else None

            # Determinar severidad basada en el nombre del evento
            category = activation.get("category", "").lower()
            salience = 0.6
            for disaster_type, default_salience in disaster_severity_map.items():
                if disaster_type.lower() in activation_name.lower() or disaster_type.lower() in category:
                    salience = default_salience
                    break

            # URL de la activación
            url = f"https://mapping.emergency.copernicus.eu/activations/{activation_code}/" if activation_code else None

            external_id = f"copernicus_{activation_code.lower()}" if activation_code else f"copernicus_{activation_name.lower().replace(' ', '_')[:30]}"

            description = activation.get("description", "")
            if not description:
                description = f"Category: {category}" if category else "Activación de respuesta de emergencia"

            events.append(
                NormalizedEvent(
                    source=self.name,
                    event_type=self.event_type,
                    title=activation_name,
                    description=description[:300],
                    url=url,
                    salience=clamp(salience),
                    event_time=event_time,
                    external_id=external_id,
                    raw={
                        "activation_code": activation_code,
                        "category": category,
                    },
                )
            )

        return events
