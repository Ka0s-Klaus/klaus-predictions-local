"""Emisión y persistencia de predicciones."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable, Sequence
from typing import Any

from sqlalchemy import select

from engine.database import session_scope
from engine.mirofish.agents.base import Agent
from engine.mirofish.swarm import MiroFishSwarm
from engine.models import AgentScore, AuditLog, Prediction, new_agent_score

logger = logging.getLogger(__name__)

DEFAULT_HORIZONS = ("24h", "week", "month", "year")

# Proveedor de contexto: devuelve los eventos recientes que verá el enjambre.
# En esta fase se inyecta desde fuera; la fase de feeds enchufará el ingestor.
ContextProvider = Callable[[str, int], Sequence[dict[str, Any]]]

# Callback de progreso: async (status: str, progress: dict) para streaming
ProgressCallback = Callable[[str, dict[str, Any]], asyncio.Awaitable[None]]


class Predictor:
    """Une el enjambre con la base de datos."""

    def __init__(
        self,
        swarm: MiroFishSwarm,
        *,
        horizons: Sequence[str] = DEFAULT_HORIZONS,
        confidence_min: float = 0.55,
        context_provider: ContextProvider | None = None,
        audit_enabled: bool = True,
    ) -> None:
        self.swarm = swarm
        self.horizons = tuple(horizons)
        self.confidence_min = confidence_min
        self.context_provider = context_provider
        self.audit_enabled = audit_enabled

    def _context(self, query: str, limit: int = 25) -> list[dict[str, Any]]:
        if self.context_provider is None:
            return []
        return list(self.context_provider(query, limit))

    async def predict(
        self,
        query: str,
        horizon: str = "24h",
        *,
        sector: str | None = None,
        persist: bool = True,
        on_progress: ProgressCallback | None = None,
    ) -> dict[str, Any]:
        """Somete la pregunta al enjambre y guarda el resultado."""
        if horizon not in self.horizons:
            raise ValueError(
                f"horizonte '{horizon}' no soportado; disponibles: {', '.join(self.horizons)}"
            )

        events = self._context(query)

        # Emite inicio
        if on_progress:
            await on_progress("started", {"agents": len(self.swarm.agents)})

        started = time.perf_counter()
        consensus = await self.swarm.run(query, {"events": events}, horizon=horizon)
        latency_ms = int((time.perf_counter() - started) * 1000)

        # Emite completado
        if on_progress:
            await on_progress("completed", {"latency_ms": latency_ms})

        result: dict[str, Any] = {
            "prediction_id": None,
            "query": query,
            "horizon": horizon,
            "prediction": consensus.prediction,
            "confidence": consensus.confidence,
            "agent_votes": consensus.agent_votes,
            "reasoning": consensus.reasoning,
            "sources_used": consensus.sources_used,
            "dissent": consensus.dissent,
            "meets_threshold": consensus.confidence >= self.confidence_min,
            "latency_ms": latency_ms,
        }

        if persist:
            result["prediction_id"] = self._persist(result, sector=sector)

        return result

    def _persist(self, result: dict[str, Any], *, sector: str | None) -> int:
        with session_scope() as session:
            row = Prediction(
                query_text=result["query"],
                sector=sector,
                horizon=result["horizon"],
                prediction_text=result["prediction"],
                probability=result["confidence"],
                agent_votes=result["agent_votes"],
                reasoning=result["reasoning"],
                sources_used=result["sources_used"],
                latency_ms=result["latency_ms"],
            )
            session.add(row)
            if self.audit_enabled:
                session.add(
                    AuditLog(
                        event_type="prediction",
                        action=result["query"][:500],
                        payload={
                            "horizon": result["horizon"],
                            "confidence": result["confidence"],
                            "dissent": result["dissent"],
                        },
                        latency_ms=result["latency_ms"],
                    )
                )
            session.flush()
            return row.id

    # ------------------------------------------------------------------
    # Calibración persistida
    # ------------------------------------------------------------------

    def load_agent_scores(self) -> None:
        """Restaura el historial de los agentes desde la base de datos.

        Sin esto, el enjambre arrancaría con todos los pesos iguales en cada
        reinicio y el voto ponderado no serviría de nada.
        """
        with session_scope() as session:
            rows = {row.agent_name: row for row in session.scalars(select(AgentScore))}

        for agent in self.swarm.agents:
            row = rows.get(agent.name)
            if row is None:
                continue
            agent.brier_score = row.brier_score
            agent.predictions_made = row.predictions_made
            agent.correct_predictions = row.correct_predictions

    def save_agent_scores(self) -> None:
        """Vuelca el historial en memoria de los agentes a la base de datos."""
        with session_scope() as session:
            existing = {row.agent_name: row for row in session.scalars(select(AgentScore))}
            for agent in self.swarm.agents:
                row = existing.get(agent.name)
                if row is None:
                    row = new_agent_score(agent.name)
                    session.add(row)
                row.brier_score = agent.brier_score
                row.predictions_made = agent.predictions_made
                row.correct_predictions = agent.correct_predictions
                row.accuracy = agent.accuracy


def build_agent_context(agents: Sequence[Agent]) -> dict[str, dict[str, float]]:
    """Vista del estado de calibración del enjambre, para `/scorecard` y logs."""
    return {
        agent.name: {
            "brier_score": round(agent.brier_score, 4),
            "weight": round(agent.weight, 4),
            "accuracy": round(agent.accuracy, 4),
            "predictions_made": agent.predictions_made,
        }
        for agent in agents
    }
