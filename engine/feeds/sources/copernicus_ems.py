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
    endpoint: ClassVar[str] = "https://emergency.copernicus.eu/mapping/activations-rapid/feed"

    def parse(self, payload: Any) -> list[NormalizedEvent]:
        """Extrae activaciones del feed RSS de Copernicus EMS."""
        import xml.etree.ElementTree as ET

        if isinstance(payload, str):
            try:
                root = ET.fromstring(payload)
            except ET.ParseError:
                return []
        else:
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

        for item in root.findall(".//item"):
            title = (item.findtext("title") or "").strip()
            if not title:
                continue

            description = (item.findtext("description") or "").strip()
            link = (item.findtext("link") or "").strip()
            pub_date = item.findtext("pubDate")

            salience = 0.6
            for disaster_type, default_salience in disaster_severity_map.items():
                if disaster_type.lower() in title.lower():
                    salience = default_salience
                    break

            event_time = parse_timestamp(pub_date) if pub_date else None

            external_id = f"copernicus_{title.lower().replace(' ', '_')[:30]}"

            events.append(
                NormalizedEvent(
                    source=self.name,
                    event_type=self.event_type,
                    title=title,
                    description=description[:300] if description else "Activación de respuesta de emergencia",
                    url=link if link else None,
                    salience=clamp(salience),
                    event_time=event_time,
                    external_id=external_id,
                    raw={
                        "title": title,
                        "link": link,
                        "pub_date": pub_date,
                    },
                )
            )

        return events
