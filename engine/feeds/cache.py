"""Caché de ingesta y retención de histórico.

Dos mecanismos distintos que a menudo se confunden:

- `TTLCache` evita volver a pedir a una fuente antes de que su intervalo haya
  vencido. Vive en memoria; se pierde al reiniciar, y da igual.
- `prune_old_events` aplica la retención de `FEEDS_CACHE_DAYS` sobre la tabla
  de eventos. Sin esto, en una máquina con 256 GB de SSD el histórico crece
  sin control.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, func, select

from engine.database import session_scope
from engine.models import FeedEvent, utcnow

logger = logging.getLogger(__name__)

SECONDS_PER_DAY = 86400


@dataclass(slots=True)
class _Entry:
    value: Any
    expires_at: float


class TTLCache:
    """Caché por clave con caducidad, con reloj inyectable para los tests."""

    def __init__(self, ttl_seconds: int = 900, clock: Callable[[], float] = time.monotonic) -> None:
        if ttl_seconds < 0:
            raise ValueError("el TTL no puede ser negativo")
        self.ttl_seconds = ttl_seconds
        self._clock = clock
        self._entries: dict[str, _Entry] = {}

    def get(self, key: str) -> Any | None:
        entry = self._entries.get(key)
        if entry is None:
            return None
        if entry.expires_at <= self._clock():
            del self._entries[key]
            return None
        return entry.value

    def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        ttl = self.ttl_seconds if ttl_seconds is None else ttl_seconds
        self._entries[key] = _Entry(value=value, expires_at=self._clock() + ttl)

    def invalidate(self, key: str) -> None:
        self._entries.pop(key, None)

    def clear(self) -> None:
        self._entries.clear()

    def __contains__(self, key: str) -> bool:
        return self.get(key) is not None

    def __len__(self) -> int:
        # Contar implica purgar lo caducado, o el número miente.
        now = self._clock()
        self._entries = {k: v for k, v in self._entries.items() if v.expires_at > now}
        return len(self._entries)


def _as_epoch(value: datetime) -> float:
    """Segundos epoch, asumiendo UTC si el motor devolvió el dato sin zona."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.timestamp()


def prune_old_events(days: int) -> int:
    """Borra los eventos anteriores a la ventana de retención.

    Devuelve cuántas filas se eliminaron. Con `days <= 0` no hace nada: se
    interpreta como retención ilimitada.
    """
    if days <= 0:
        return 0

    cutoff = utcnow().timestamp() - days * SECONDS_PER_DAY
    with session_scope() as session:
        # Se filtra en Python porque SQLite guarda los datetimes como texto y
        # los devuelve sin zona horaria: comparar en SQL no es fiable entre
        # motores.
        stale = [
            row_id
            for row_id, ingested in session.execute(
                select(FeedEvent.id, FeedEvent.ingestion_time)
            ).all()
            if ingested is not None and _as_epoch(ingested) < cutoff
        ]
        if not stale:
            return 0
        session.execute(delete(FeedEvent).where(FeedEvent.id.in_(stale)))
        logger.info("Purgados %d eventos anteriores a %d días", len(stale), days)
        return len(stale)


def event_counts() -> dict[str, int]:
    """Eventos almacenados por fuente."""
    with session_scope() as session:
        rows = session.execute(
            select(FeedEvent.source, func.count(FeedEvent.id)).group_by(FeedEvent.source)
        ).all()
    return {source: count for source, count in rows}
