"""Aplicación FastAPI y estado compartido del proceso."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime

from fastapi import FastAPI

from engine import __version__, database
from engine.api import middleware
from engine.config import Settings, get_settings
from engine.feeds import FeedIngestor, recent_events
from engine.llm import OllamaClient
from engine.mirofish import MiroFishSwarm, build_agents
from engine.models import utcnow
from engine.prediction import Predictor

logger = logging.getLogger(__name__)


@dataclass
class PythiaState:
    """Todo lo que se construye una vez y se comparte entre peticiones."""

    settings: Settings
    llm: OllamaClient
    swarm: MiroFishSwarm
    predictor: Predictor
    ingestor: FeedIngestor
    started_at: datetime = field(default_factory=utcnow)
    ingestion_task: asyncio.Task[None] | None = None

    @property
    def uptime_seconds(self) -> int:
        return int((utcnow() - self.started_at).total_seconds())


def build_state(settings: Settings | None = None) -> PythiaState:
    """Monta el grafo de objetos. No toca la red ni la base de datos."""
    settings = settings or get_settings()
    llm = OllamaClient(settings.ollama)
    agents = build_agents(llm, limit=settings.mirofish.agents)
    swarm = MiroFishSwarm(
        agents,
        llm,
        consensus_threshold=settings.mirofish.consensus_threshold,
        brier_weighted=settings.mirofish.brier_weighted_voting,
    )
    predictor = Predictor(
        swarm,
        horizons=settings.prediction.horizons,
        confidence_min=settings.prediction.confidence_min,
        # El contexto sale de la base de datos, no de una ingesta en caliente:
        # una predicción no puede quedarse esperando a 8 descargas HTTP.
        context_provider=lambda _query, limit: recent_events(limit=limit),
        audit_enabled=settings.audit_enabled,
    )
    return PythiaState(
        settings=settings,
        llm=llm,
        swarm=swarm,
        predictor=predictor,
        ingestor=FeedIngestor(),
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    database.init_db()

    state = build_state(settings)
    # Sin esto, el voto ponderado arrancaría plano en cada reinicio.
    state.predictor.load_agent_scores()
    app.state.pythia = state

    if settings.feeds.enabled:
        state.ingestion_task = asyncio.create_task(state.ingestor.run_forever())
        logger.info("Ingesta en segundo plano cada %ds", settings.feeds.update_interval)

    logger.info(
        "Pythia lista: %d agentes, %d fuentes, horizontes %s",
        len(state.swarm.agents),
        len(state.ingestor.sources),
        ", ".join(settings.prediction.horizons),
    )

    try:
        yield
    finally:
        if state.ingestion_task is not None:
            state.ingestion_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await state.ingestion_task
        # El historial vive en memoria durante la sesión; si no se vuelca aquí,
        # se pierde todo lo aprendido.
        with contextlib.suppress(Exception):
            state.predictor.save_agent_scores()
        await state.llm.close()
        logger.info("Pythia detenida")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Pythia Oracle",
        description=(
            "Oráculo de predicción local-first: feeds públicos, enjambre de "
            "agentes y LLM ejecutándose en la propia máquina."
        ),
        version=__version__,
        lifespan=lifespan,
    )
    middleware.install(app)

    from engine.api.routes import router

    app.include_router(router)
    return app
