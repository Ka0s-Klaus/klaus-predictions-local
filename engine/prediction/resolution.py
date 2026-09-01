"""Resolución de predicciones vencidas.

Una predicción sin resolver no informa de nada: hasta que no se registra el
desenlace no hay Brier score, y sin Brier el voto ponderado del enjambre es
voto plano. Este módulo cierra ese bucle.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from sqlalchemy import select

from engine.database import session_scope
from engine.mirofish.agents.base import CORRECTNESS_MARGIN
from engine.models import AgentScore, Prediction, new_agent_score, utcnow
from engine.prediction.brier import brier_score

logger = logging.getLogger(__name__)

# Cuánto dura cada horizonte antes de considerarse vencido.
HORIZON_DELTAS: dict[str, timedelta] = {
    "24h": timedelta(hours=24),
    "week": timedelta(days=7),
    "month": timedelta(days=30),
    "year": timedelta(days=365),
}


def due_predictions(limit: int = 100) -> list[Prediction]:
    """Predicciones cuyo horizonte ya venció y siguen sin resolver."""
    now = utcnow()
    with session_scope() as session:
        candidates = session.scalars(
            select(Prediction).where(Prediction.resolved.is_(False)).limit(limit * 4)
        ).all()

    due = []
    for row in candidates:
        delta = HORIZON_DELTAS.get(row.horizon)
        if delta is None:
            logger.warning("Horizonte desconocido en la predicción %s: %s", row.id, row.horizon)
            continue
        created = row.created_at
        if created.tzinfo is None:
            # SQLite devuelve datetimes naive aunque la columna sea timezone-aware.
            created = created.replace(tzinfo=now.tzinfo)
        if created + delta <= now:
            due.append(row)
        if len(due) >= limit:
            break
    return due


def resolve(prediction_id: int, outcome: float, notes: str | None = None) -> float:
    """Registra el desenlace de una predicción y devuelve su Brier score.

    `outcome` es 1.0 si ocurrió y 0.0 si no. Se admiten valores intermedios para
    desenlaces parciales.
    """
    if not 0.0 <= outcome <= 1.0:
        raise ValueError(f"el desenlace debe estar entre 0 y 1, llegó {outcome}")

    with session_scope() as session:
        row = session.get(Prediction, prediction_id)
        if row is None:
            raise LookupError(f"no existe la predicción {prediction_id}")
        if row.resolved:
            raise ValueError(f"la predicción {prediction_id} ya estaba resuelta")

        score = brier_score(row.probability, outcome)
        row.resolved = True
        row.outcome_value = outcome
        row.actual_outcome = notes
        row.brier_score = score
        row.resolution_time = utcnow()

        _apply_to_agents(session, row.agent_votes or {}, outcome)
        return score


def _apply_to_agents(session, agent_votes: dict[str, float], outcome: float) -> None:
    """Actualiza el marcador de cada agente que votó esta predicción."""
    if not agent_votes:
        return

    existing = {row.agent_name: row for row in session.scalars(select(AgentScore))}

    for name, vote in agent_votes.items():
        if not isinstance(vote, (int, float)):
            continue
        row = existing.get(name)
        if row is None:
            row = new_agent_score(name)
            session.add(row)
            existing[name] = row

        score = brier_score(float(vote), outcome)
        total = row.brier_score * row.predictions_made + score
        row.predictions_made += 1
        row.brier_score = total / row.predictions_made
        if abs(vote - outcome) < CORRECTNESS_MARGIN:
            row.correct_predictions += 1
        row.accuracy = row.correct_predictions / row.predictions_made
