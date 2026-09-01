"""Normalización de eventos.

Cada fuente habla su propio dialecto: GeoJSON, JSON plano, arrays sueltos. Todo
acaba en `NormalizedEvent`, que es lo único que ven el resto de módulos.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from engine.models import FeedEvent

# Límites de la columna correspondiente en la base de datos.
MAX_TITLE = 500
MAX_URL = 500
MAX_DESCRIPTION = 4000


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def truncate(text: str | None, limit: int) -> str | None:
    if text is None:
        return None
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def parse_timestamp(value: Any) -> datetime | None:
    """Interpreta los formatos de fecha que devuelven las fuentes.

    Acepta epoch en segundos o milisegundos, e ISO-8601 con `Z`.
    """
    if value is None or value == "":
        return None

    if isinstance(value, datetime):
        return value

    if isinstance(value, (int, float)):
        # Por encima de esta cota el número sólo puede estar en milisegundos:
        # como segundos caería en el año 33658.
        seconds = value / 1000 if value > 1e11 else value
        try:
            return datetime.fromtimestamp(seconds, tz=UTC)
        except (OverflowError, OSError, ValueError):
            return None

    if isinstance(value, str):
        text = value.strip().replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(text)
        except ValueError:
            return None

    return None


@dataclass(slots=True)
class NormalizedEvent:
    """Un evento ya homogeneizado, listo para persistir."""

    source: str
    title: str
    event_type: str | None = None
    description: str | None = None
    url: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    magnitude: float | None = None
    salience: float = 0.5
    event_time: datetime | None = None
    external_id: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.title = truncate(self.title, MAX_TITLE) or "(sin título)"
        self.description = truncate(self.description, MAX_DESCRIPTION)
        self.url = truncate(self.url, MAX_URL)
        self.salience = clamp(self.salience)
        # Coordenadas fuera de rango son un error de parseo, no un dato: si se
        # dejan pasar, el CHECK de la tabla aborta toda la transacción.
        if self.latitude is not None and not -90 <= self.latitude <= 90:
            self.latitude = None
        if self.longitude is not None and not -180 <= self.longitude <= 180:
            self.longitude = None

    def to_model(self) -> FeedEvent:
        return FeedEvent(
            source=self.source,
            event_type=self.event_type,
            latitude=self.latitude,
            longitude=self.longitude,
            magnitude=self.magnitude,
            title=self.title,
            description=self.description,
            url=self.url,
            salience=self.salience,
            event_time=self.event_time,
            external_id=self.external_id,
            raw_json=self.raw or None,
        )

    def to_dict(self) -> dict[str, Any]:
        """Forma compacta: es lo que se le pasa al prompt del enjambre."""
        return {
            "source": self.source,
            "event_type": self.event_type,
            "title": self.title,
            "salience": self.salience,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "event_time": self.event_time.isoformat() if self.event_time else None,
            "url": self.url,
        }


def dedupe(events: list[NormalizedEvent]) -> list[NormalizedEvent]:
    """Elimina repetidos por `(source, external_id)`, conservando el primero."""
    seen: set[tuple[str, str]] = set()
    unique: list[NormalizedEvent] = []
    for event in events:
        if event.external_id is None:
            unique.append(event)
            continue
        key = (event.source, event.external_id)
        if key not in seen:
            seen.add(key)
            unique.append(event)
    return unique
