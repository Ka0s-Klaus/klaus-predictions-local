"""GloFAS — sistema global de alerta temprana de inundaciones."""

from __future__ import annotations

from typing import Any, ClassVar

from engine.feeds.normalizer import NormalizedEvent, clamp, parse_timestamp
from engine.feeds.sources.base import FeedSource


class GloFASFloods(FeedSource):
    """Monitorea alertas de inundación de GloFAS Copernicus.

    NOTE: GloFAS public API endpoint is not currently stable. Data is available through
    the Climate Data Store (CDS) at https://cds.climate.copernicus.eu/ but requires
    authentication and manual data retrieval. This feed is currently disabled and returns
    empty results. To enable, implement CDS API client authentication or find alternative
    public flood alert API endpoint.
    """

    name: ClassVar[str] = "GloFAS"
    domain: ClassVar[str] = "disasters"
    event_type: ClassVar[str] = "flood_alert"
    endpoint: ClassVar[str] = "https://global-flood.emergency.copernicus.eu/api/v2/floods/"

    def parse(self, payload: Any) -> list[NormalizedEvent]:
        """Extrae eventos de inundación del API de GloFAS.

        Nota: El endpoint público de GloFAS no está disponible actualmente.
        Retorna lista vacía hasta que se encuentre una fuente de datos alternativa.
        """
        # GloFAS public API endpoint is not currently stable/available
        # Return empty list as placeholder
        return []
