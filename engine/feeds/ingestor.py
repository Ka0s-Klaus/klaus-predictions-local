"""Ingesta concurrente de fuentes."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

import aiohttp
from sqlalchemy import func, select
from sqlalchemy.orm import aliased

from engine.config import get_settings
from engine.database import session_scope
from engine.feeds.cache import TTLCache
from engine.feeds.normalizer import NormalizedEvent, dedupe
from engine.feeds.registry import build_sources
from engine.feeds.sources import FeedError, FeedSource
from engine.models import FeedEvent

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class IngestionReport:
    """Qué ha pasado en una ronda de ingesta."""

    events: list[NormalizedEvent] = field(default_factory=list)
    succeeded: list[str] = field(default_factory=list)
    failed: dict[str, str] = field(default_factory=dict)
    from_cache: list[str] = field(default_factory=list)
    persisted: int = 0

    @property
    def attempted(self) -> int:
        return len(self.succeeded) + len(self.failed) + len(self.from_cache)

    def to_dict(self) -> dict[str, Any]:
        return {
            "events": len(self.events),
            "persisted": self.persisted,
            "succeeded": sorted(self.succeeded),
            "failed": self.failed,
            "from_cache": sorted(self.from_cache),
        }


class FeedIngestor:
    """Descarga todas las fuentes en paralelo y guarda lo que llega.

    Una fuente que falla no puede tumbar la ronda: se anota en el informe y las
    demás siguen. Es la razón de que la ingesta use `return_exceptions=True`.
    """

    def __init__(
        self,
        sources: Sequence[FeedSource] | None = None,
        *,
        concurrency: int | None = None,
        timeout: int | None = None,
        cache: TTLCache | None = None,
    ) -> None:
        settings = get_settings().feeds
        self.concurrency = concurrency or settings.concurrency
        self.timeout = timeout or settings.timeout
        self.cache = cache if cache is not None else TTLCache(settings.update_interval)
        self.sources = list(
            sources
            if sources is not None
            else build_sources(max_bytes=settings.max_feed_size_mb * 1024 * 1024)
        )

    async def ingest_all(self, session: aiohttp.ClientSession | None = None) -> IngestionReport:
        """Una ronda completa de ingesta."""
        report = IngestionReport()
        if not self.sources:
            logger.warning("No hay fuentes implementadas que ingerir")
            return report

        owns_session = session is None
        if session is None:
            session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout + 5))

        try:
            semaphore = asyncio.Semaphore(self.concurrency)
            results = await asyncio.gather(
                *(self._fetch_one(source, session, semaphore) for source in self.sources),
                return_exceptions=True,
            )
        finally:
            if owns_session:
                await session.close()

        for source, result in zip(self.sources, results, strict=True):
            # `gather(return_exceptions=True)` devuelve el objeto excepción, que
            # NO es None. Filtrar por `is not None` — como hacía la
            # especificación — colaba las excepciones como si fueran eventos.
            if isinstance(result, BaseException):
                logger.warning("%s falló: %s", source.name, result)
                report.failed[source.name] = str(result)
                continue
            events, cached = result
            (report.from_cache if cached else report.succeeded).append(source.name)
            report.events.extend(events)

        report.events = dedupe(report.events)
        return report

    async def _fetch_one(
        self,
        source: FeedSource,
        session: aiohttp.ClientSession,
        semaphore: asyncio.Semaphore,
    ) -> tuple[list[NormalizedEvent], bool]:
        cached = self.cache.get(source.name)
        if cached is not None:
            return cached, True

        async with semaphore:
            try:
                events = await asyncio.wait_for(source.fetch(session), timeout=self.timeout)
            except TimeoutError as exc:
                raise FeedError(f"{source.name}: sin respuesta en {self.timeout}s") from exc

        self.cache.set(source.name, events)
        return events, False

    def persist(self, events: Sequence[NormalizedEvent]) -> int:
        """Guarda los eventos nuevos. Devuelve cuántos se insertaron.

        La deduplicación es por `(source, external_id)`: reingerir la misma
        ronda no debe duplicar filas.
        """
        if not events:
            return 0

        candidatos = [e for e in events if e.external_id is not None]
        sin_id = [e for e in events if e.external_id is None]

        with session_scope() as session:
            existentes: set[tuple[str, str]] = set()
            if candidatos:
                fuentes = {e.source for e in candidatos}
                ids = {e.external_id for e in candidatos}
                existentes = {
                    (source, external_id)
                    for source, external_id in session.execute(
                        select(FeedEvent.source, FeedEvent.external_id).where(
                            FeedEvent.source.in_(fuentes),
                            FeedEvent.external_id.in_(ids),
                        )
                    ).all()
                }

            nuevos = [
                event
                for event in candidatos
                if (event.source, event.external_id) not in existentes
            ]
            nuevos.extend(sin_id)

            session.add_all([event.to_model() for event in nuevos])
            return len(nuevos)

    async def run_once(self) -> IngestionReport:
        """Ingesta y persistencia en un solo paso."""
        report = await self.ingest_all()
        report.persisted = self.persist(report.events)
        logger.info(
            "Ingesta: %d eventos, %d nuevos, %d fuentes ok, %d con error",
            len(report.events),
            report.persisted,
            len(report.succeeded),
            len(report.failed),
        )
        return report

    async def run_forever(self, interval: int | None = None) -> None:
        """Bucle de ingesta. Pensado para ejecutarse como tarea de fondo."""
        period = interval or get_settings().feeds.update_interval
        while True:
            try:
                await self.run_once()
            except asyncio.CancelledError:
                logger.info("Ingesta cancelada")
                raise
            except Exception:
                # Un fallo en una ronda no puede terminar el bucle: es el
                # proceso que mantiene vivo el contexto del oráculo.
                logger.exception("La ronda de ingesta falló por completo")
            await asyncio.sleep(period)


def _balance_by_source(
    rows: list[FeedEvent],
    limit: int,
    per_source_quota: int | None,
) -> list[FeedEvent]:
    """Reparte los huecos entre fuentes en vez de dárselos todos a la más ruidosa.

    Sin esto, NWS —que publica un aviso por cada zona afectada— copa el
    contexto y el enjambre no llega a ver el terremoto, la señal geopolítica ni
    el desplome de un mercado.

    El cupo es una **reserva, no un tope**: en la primera pasada cada fuente se
    lleva como mucho `per_source_quota` huecos, lo que garantiza representación
    a las minoritarias. Si después sobran huecos se rellenan por relevancia sin
    mirar la fuente, porque devolver un contexto a medias desperdicia tokens
    que ya estaban pagados.
    """
    if not rows:
        return []

    cupo = per_source_quota if per_source_quota is not None else max(2, limit // 4)

    por_fuente: dict[str, int] = {}
    elegidos: list[FeedEvent] = []
    descartados: list[FeedEvent] = []

    for row in rows:
        usados = por_fuente.get(row.source, 0)
        if usados < cupo and len(elegidos) < limit:
            por_fuente[row.source] = usados + 1
            elegidos.append(row)
        else:
            descartados.append(row)

    # Segunda pasada: si el reparto dejó huecos, se llenan sin mirar la fuente.
    for row in descartados:
        if len(elegidos) >= limit:
            break
        elegidos.append(row)

    elegidos.sort(key=lambda r: (-(r.salience or 0.0), r.source))
    return elegidos


def recent_events(
    limit: int = 25,
    min_salience: float = 0.0,
    per_source_quota: int | None = None,
) -> list[dict[str, Any]]:
    """Eventos más recientes y relevantes. Es el contexto que ve el enjambre.

    Dos filtros, ambos por el mismo motivo: el contexto son 4096 tokens y hay
    que dejar sitio para siete dictámenes.

    - Títulos repetidos: fuentes como NWS emiten el mismo aviso para cada zona
      afectada, con identificadores distintos. Son filas legítimas en la tabla,
      pero tres líneas idénticas no aportan nada al razonamiento.
    - Reparto por fuente: ninguna fuente puede acaparar el contexto.

    El reparto tiene que empezar en la consulta. Pedir simplemente las N filas
    más relevantes devuelve una ventana ya sesgada: NWS y EONET copan la franja
    alta y fuentes de saliencia estructuralmente baja — divisas, cripto, GDELT —
    no llegan ni a entrar en el conjunto de candidatos.
    """
    quota = per_source_quota if per_source_quota is not None else max(2, limit // 4)
    # Margen sobre el cupo para que el filtrado de títulos tenga de dónde tirar.
    por_fuente = max(limit, quota * 4)

    with session_scope() as session:
        ranked = (
            select(
                FeedEvent,
                func.row_number()
                .over(
                    partition_by=FeedEvent.source,
                    order_by=(FeedEvent.salience.desc(), FeedEvent.ingestion_time.desc()),
                )
                .label("rn"),
            )
            .where(FeedEvent.salience >= min_salience)
            .subquery()
        )
        evento = aliased(FeedEvent, ranked)
        rows = session.scalars(
            select(evento)
            .where(ranked.c.rn <= por_fuente)
            .order_by(ranked.c.salience.desc(), ranked.c.ingestion_time.desc())
        ).all()

    vistos: set[str] = set()
    unicos = []
    for row in rows:
        clave = (row.title or "").strip().casefold()
        if clave in vistos:
            continue
        vistos.add(clave)
        unicos.append(row)

    seleccion = _balance_by_source(unicos, limit, quota)

    return [
        {
            "source": row.source,
            "event_type": row.event_type,
            "title": row.title,
            "salience": row.salience,
            "latitude": row.latitude,
            "longitude": row.longitude,
            "event_time": row.event_time.isoformat() if row.event_time else None,
            "url": row.url,
        }
        for row in seleccion
    ]
