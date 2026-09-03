"""Elexon BMRS — dados de desequilibrio de la red eléctrica del Reino Unido."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import ClassVar

import aiohttp

from engine.feeds.normalizer import NormalizedEvent, clamp, parse_timestamp
from engine.feeds.sources.base import FeedError, FeedSource, USER_AGENT


class ElexonBMRS(FeedSource):
    """Datos de desequilibrio de la red eléctrica (British Market Imbalance Prices)."""

    name: ClassVar[str] = "Elexon"
    domain: ClassVar[str] = "energy"
    event_type: ClassVar[str] = "grid_imbalance"
    endpoint: ClassVar[str] = (
        "https://api.elexon.co.uk/BMRS/api/rawdata/latest/data"
        "?element=MELIMBALNGC&apiVersion=v1"
    )

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
        """Parsea XML de datos BMRS de desequilibrio de red."""
        events = []
        try:
            root = ET.fromstring(payload)
        except ET.ParseError as exc:
            raise FeedError(f"{self.name}: XML inválido — {exc}") from exc

        # Buscar datos de imbalance (wildcards para ignorar namespaces)
        for data_elem in root.findall(".//data"):
            # Extraer timestamp
            timestamp_elem = data_elem.find(".//timestamp")
            timestamp = None
            if timestamp_elem is not None and timestamp_elem.text:
                timestamp = parse_timestamp(timestamp_elem.text)

            # Extraer métrica principal (MELIMBALNGC - Metering Estimate of Linked Net
            # Generation Capacity Imbalance)
            value_elem = data_elem.find(".//value")
            value = None
            if value_elem is not None and value_elem.text:
                try:
                    value = float(value_elem.text)
                except ValueError:
                    pass

            # Información adicional
            unit_elem = data_elem.find(".//unit")
            unit = (unit_elem.text if unit_elem is not None else "").strip() or "MW"

            metric_elem = data_elem.find(".//metric")
            metric = (metric_elem.text if metric_elem is not None else "").strip() or "MELIMBALNGC"

            if value is None:
                continue

            # Calcular salience basada en magnitud del desequilibrio
            # Valores absolutos grandes indican estrés en la red
            abs_value = abs(value)
            salience = self._calculate_salience(abs_value)

            # Generar ID único basado en timestamp y métrica
            external_id = self._generate_id(timestamp, metric)

            # Determinar dirección del desequilibrio (positivo = exceso, negativo = déficit)
            direction = "surplus" if value > 0 else "deficit"

            title = f"Grid Imbalance: {direction.capitalize()}"
            description = f"{metric}: {value:+.1f} {unit}"

            events.append(
                NormalizedEvent(
                    source=self.name,
                    event_type=self.event_type,
                    title=title,
                    description=description,
                    magnitude=value,
                    salience=salience,
                    event_time=timestamp,
                    external_id=external_id,
                    raw={
                        "metric": metric,
                        "value": value,
                        "unit": unit,
                        "direction": direction,
                    },
                )
            )

        return events

    @staticmethod
    def _calculate_salience(abs_value: float) -> float:
        """Calcula salience basada en magnitud del desequilibrio."""
        # Escala de referencia: 1000 MW es un desequilibrio significativo
        # 5000 MW es crítico
        if abs_value < 500:
            return clamp(0.2)
        elif abs_value < 1000:
            return clamp(0.4)
        elif abs_value < 2000:
            return clamp(0.6)
        elif abs_value < 5000:
            return clamp(0.8)
        else:
            return clamp(1.0)

    @staticmethod
    def _generate_id(timestamp: datetime | None, metric: str) -> str:
        """Genera ID único basado en timestamp y métrica."""
        import hashlib

        if timestamp:
            combined = f"{timestamp.isoformat()}_{metric}"
        else:
            combined = metric
        return hashlib.md5(combined.encode()).hexdigest()[:16]
