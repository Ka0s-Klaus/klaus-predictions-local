"""USGS — monitoreo de niveles de agua y caudal de ríos."""

from __future__ import annotations

from typing import Any, ClassVar

from engine.feeds.normalizer import NormalizedEvent, clamp, parse_timestamp
from engine.feeds.sources.base import FeedSource


class USGSWater(FeedSource):
    """Monitorea niveles de agua en sitios de medición USGS."""

    name: ClassVar[str] = "USGS-Water"
    domain: ClassVar[str] = "disasters"
    event_type: ClassVar[str] = "water_level"
    endpoint: ClassVar[str] = (
        "https://waterservices.usgs.gov/nwis/site/?format=json&stateCd=CA&siteType=ST&period=P1D"
    )

    def parse(self, payload: Any) -> list[NormalizedEvent]:
        """Extrae datos de niveles de agua de la API USGS."""
        if not isinstance(payload, dict):
            return []

        value_data = payload.get("value", {})
        if not isinstance(value_data, dict):
            return []

        timeseries_list = value_data.get("timeSeries", [])
        if not isinstance(timeseries_list, list):
            return []

        events = []
        for ts in timeseries_list:
            if not isinstance(ts, dict):
                continue

            # Extraer información del sitio
            source_info = ts.get("sourceInfo", {})
            if not isinstance(source_info, dict):
                continue

            site_no = source_info.get("siteName", "").strip()
            if not site_no:
                site_no = source_info.get("siteCode", [{}])[0].get("value", "").strip()

            if not site_no:
                continue

            # Extraer coordenadas
            geolocation = source_info.get("geoLocation", {})
            geolocation_point = geolocation.get("geogLocation", {})
            try:
                lat = float(geolocation_point.get("srs1", {}).get("latitude", 0))
                lon = float(geolocation_point.get("srs1", {}).get("longitude", 0))
            except (ValueError, TypeError, AttributeError):
                lat = lon = None

            # Obtener última medición
            values = ts.get("values", [{}])[0]
            if not isinstance(values, dict):
                continue

            value_list = values.get("value", [])
            if not value_list:
                continue

            # Tomar el último valor
            last_value = value_list[-1]
            if not isinstance(last_value, dict):
                continue

            discharge = last_value.get("value", "")
            if not discharge:
                continue

            try:
                discharge = float(discharge)
            except (ValueError, TypeError):
                continue

            # Salience basada en anomalía de caudal (estimado)
            salience = clamp(0.4 + min(discharge / 1000.0, 0.6))

            external_id = site_no.lower().replace(" ", "_")

            events.append(
                NormalizedEvent(
                    source=self.name,
                    event_type=self.event_type,
                    title=f"Water Level: {site_no}",
                    description=f"Stream discharge: {discharge:.1f} cubic feet per second",
                    magnitude=discharge,
                    salience=salience,
                    latitude=lat if lat and -90 <= lat <= 90 else None,
                    longitude=lon if lon and -180 <= lon <= 180 else None,
                    event_time=None,
                    external_id=external_id,
                    raw={
                        "site_no": site_no,
                        "discharge_cfs": round(discharge, 2),
                    },
                )
            )

        return events
