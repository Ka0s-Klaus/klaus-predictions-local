"""PTWC — alertas de tsunami del Centro de Alerta de Tsunami del Pacífico."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import ClassVar

import aiohttp

from engine.feeds.normalizer import NormalizedEvent, clamp, parse_timestamp
from engine.feeds.sources.base import FeedError, FeedSource, USER_AGENT


class PTWCTsunami(FeedSource):
    """Alertas de tsunami del Pacific Tsunami Warning Center (PTWC)."""

    name: ClassVar[str] = "PTWC"
    domain: ClassVar[str] = "disasters"
    event_type: ClassVar[str] = "tsunami_alert"
    endpoint: ClassVar[str] = "https://www.tsunami.gov/events/xml/PHEBCAP.xml"

    async def fetch(self, session: aiohttp.ClientSession) -> list[NormalizedEvent]:
        """Descarga e interpreta XML. Lanza `FeedError` si algo va mal."""
        xml_text = await self._request_text(session, self.endpoint)
        try:
            events = self.parse(xml_text)
        except FeedError:
            raise
        except Exception as exc:
            raise FeedError(f"{self.name}: la respuesta no encaja con el parser: {exc}") from exc
        return events

    async def _request_text(self, session: aiohttp.ClientSession, url: str) -> str:
        """Descarga la respuesta como texto."""
        headers = {"User-Agent": USER_AGENT, **self.headers}
        try:
            async with session.get(url, headers=headers) as response:
                if response.status != 200:
                    body = (await response.text())[:200]
                    raise FeedError(f"{self.name}: HTTP {response.status} — {body}")

                raw = await response.read()
                if len(raw) > self.max_bytes:
                    raise FeedError(
                        f"{self.name}: {len(raw)} bytes superan el límite de {self.max_bytes}"
                    )
                return raw.decode("utf-8", errors="replace")
        except aiohttp.ClientError as exc:
            raise FeedError(f"{self.name}: fallo de red — {exc}") from exc

    def parse(self, payload: str) -> list[NormalizedEvent]:
        """Parsea XML y extrae eventos de alerta de tsunami."""
        events = []
        try:
            root = ET.fromstring(payload)
        except ET.ParseError as exc:
            raise FeedError(f"{self.name}: XML inválido — {exc}") from exc

        # Buscar elementos evento (wildcards para cualquier namespace)
        for event in root.findall(".//event"):
            # Intentar extraer información del evento
            event_id = event.get("id") or ""
            title_elem = event.find(".//title")
            title = (title_elem.text if title_elem is not None else "").strip()

            if not title:
                title = f"Tsunami Event {event_id}"

            description_elem = event.find(".//summary")
            description = (description_elem.text if description_elem is not None else "").strip()

            link_elem = event.find(".//link")
            link = link_elem.get("href") if link_elem is not None else ""

            # Extraer información de epicentro si existe
            magnitude = self._extract_magnitude(event)
            latitude = None
            longitude = None

            epicenter = event.find(".//epicenter")
            if epicenter is not None:
                lat_elem = epicenter.find(".//latitude")
                lon_elem = epicenter.find(".//longitude")
                if lat_elem is not None and lat_elem.text:
                    try:
                        latitude = float(lat_elem.text)
                    except ValueError:
                        pass
                if lon_elem is not None and lon_elem.text:
                    try:
                        longitude = float(lon_elem.text)
                    except ValueError:
                        pass

            # Fecha del evento
            time_elem = event.find(".//time")
            event_time = None
            if time_elem is not None and time_elem.text:
                event_time = parse_timestamp(time_elem.text)

            # Calcular salience: 0.8 + (magnitude / 10)
            salience = 0.8
            if magnitude is not None:
                salience = clamp(0.8 + (magnitude / 10))

            events.append(
                NormalizedEvent(
                    source=self.name,
                    event_type=self.event_type,
                    title=title,
                    description=description,
                    url=link,
                    latitude=latitude,
                    longitude=longitude,
                    magnitude=magnitude,
                    salience=salience,
                    event_time=event_time,
                    external_id=event_id,
                    raw={"event_id": event_id},
                )
            )

        return events

    @staticmethod
    def _extract_magnitude(event: ET.Element) -> float | None:
        """Extrae magnitud del terremoto que dispara el tsunami."""
        magnitude_elem = event.find(".//magnitude")
        if magnitude_elem is not None and magnitude_elem.text:
            try:
                return float(magnitude_elem.text)
            except ValueError:
                pass
        return None
