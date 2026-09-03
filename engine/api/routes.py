"""Los nueve endpoints de la API."""

from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select

from engine import __version__
from engine.api.app import PythiaState
from engine.api.auth import verify_token
from engine.api.websocket import state_stream
from engine.database import session_scope
from engine.feeds import event_counts, recent_events, summary
from engine.models import FeedEvent, Prediction, utcnow
from engine.prediction import build_agent_context, calibration

logger = logging.getLogger(__name__)

router = APIRouter()
protected = APIRouter(dependencies=[Depends(verify_token)])

DOMAINS = ("geopolitical", "markets", "energy", "disasters", "climate")


def get_state(request: Request) -> PythiaState:
    state = getattr(request.app.state, "pythia", None)
    if state is None:  # pragma: no cover - sólo si se salta el lifespan
        raise HTTPException(status_code=503, detail="La aplicación aún no ha arrancado")
    return state


State = Annotated[PythiaState, Depends(get_state)]


# ---------------------------------------------------------------------
# Modelos de petición
# ---------------------------------------------------------------------


class PredictRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    horizon: str = "24h"
    min_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    sector: str | None = None


class ChatRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    # La especificación usa `agent`; el documento de instalación escribía
    # `person` en un ejemplo. Manda `agent`, y se acepta `person` como alias
    # para no romper a quien copiara aquel ejemplo.
    agent: str = Field(default="Strategist", validation_alias="agent")

    model_config = {"populate_by_name": True, "extra": "allow"}

    def resolved_agent(self) -> str:
        extra = self.model_extra or {}
        return str(extra.get("person") or self.agent)


class WhatIfRequest(BaseModel):
    scenario: str = Field(min_length=1, max_length=2000)
    context: str | None = None
    horizon: str = "week"


# ---------------------------------------------------------------------
# 1. Salud
# ---------------------------------------------------------------------


@router.get("/health", summary="Estado del servicio")
async def health(state: State) -> dict[str, Any]:
    """Sin autenticación a propósito: lo consultan los supervisores de proceso."""
    return {
        "status": "ok",
        "version": __version__,
        "timestamp": utcnow().isoformat(),
        "uptime_seconds": state.uptime_seconds,
        "agents": len(state.swarm.agents),
        "feeds": summary(),
        "horizons": list(state.predictor.horizons),
    }


@protected.get("/health/llm", summary="¿Responde el modelo?")
async def health_llm(state: State) -> dict[str, Any]:
    available = await state.llm.is_available()
    return {
        "available": available,
        "model": state.settings.ollama.model_name,
        "base_url": state.settings.ollama.base_url,
    }


# ---------------------------------------------------------------------
# 2-3. Estado del mundo
# ---------------------------------------------------------------------


@protected.get("/agent/view", summary="Resumen del estado del mundo")
async def agent_view(
    state: State,
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
) -> dict[str, Any]:
    events = await run_in_threadpool(recent_events, limit=limit)
    return {
        "summary": f"Estado del mundo: {len(events)} señales destacadas",
        "timestamp": utcnow().isoformat(),
        "domains": list(DOMAINS),
        "events": events,
        "sources_active": await run_in_threadpool(event_counts),
    }


@protected.get("/agent/events", summary="Eventos ingeridos")
async def agent_events(
    source: str | None = None,
    min_salience: Annotated[float, Query(ge=0.0, le=1.0)] = 0.0,
    limit: Annotated[int, Query(ge=1, le=500)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict[str, Any]:
    def query() -> tuple[list[dict[str, Any]], int]:
        with session_scope() as session:
            stmt = select(FeedEvent).where(FeedEvent.salience >= min_salience)
            if source:
                stmt = stmt.where(FeedEvent.source == source)

            total = len(session.scalars(stmt).all())
            rows = session.scalars(
                stmt.order_by(FeedEvent.ingestion_time.desc()).offset(offset).limit(limit)
            ).all()

            return [
                {
                    "id": row.id,
                    "source": row.source,
                    "event_type": row.event_type,
                    "title": row.title,
                    "description": row.description,
                    "latitude": row.latitude,
                    "longitude": row.longitude,
                    "magnitude": row.magnitude,
                    "salience": row.salience,
                    "url": row.url,
                    "ingestion_time": row.ingestion_time.isoformat(),
                    "event_time": row.event_time.isoformat() if row.event_time else None,
                }
                for row in rows
            ], total

    events, total = await run_in_threadpool(query)
    return {"events": events, "total": total, "limit": limit, "offset": offset}


# ---------------------------------------------------------------------
# 4-6. Razonamiento
# ---------------------------------------------------------------------


@protected.post("/predict", summary="Predicción del enjambre")
async def predict(body: PredictRequest, state: State) -> dict[str, Any]:
    """Una sola llamada al modelo produce los dictámenes de los siete agentes.

    En un i5 de 6ª generación con Mistral 7B esto tarda **minutos**, no
    segundos. Ver `docs/HARDWARE.md`.
    """
    if body.horizon not in state.predictor.horizons:
        raise HTTPException(
            status_code=400,
            detail=(
                f"horizonte '{body.horizon}' no soportado; "
                f"disponibles: {', '.join(state.predictor.horizons)}"
            ),
        )

    result = await state.predictor.predict(body.query, body.horizon, sector=body.sector)

    umbral = (
        body.min_confidence if body.min_confidence is not None else state.predictor.confidence_min
    )
    result["meets_threshold"] = result["confidence"] >= umbral
    result["threshold"] = umbral
    result["timestamp"] = utcnow().isoformat()
    return result


@protected.post("/predict/stream", summary="Predicción con progreso en vivo (SSE)")
async def predict_stream(body: PredictRequest, state: State) -> StreamingResponse:
    """Streaming de predicción con eventos de progreso en tiempo real.

    Emite eventos Server-Sent Events (SSE):
    - "started": al comenzar la predicción
    - "completed": al terminar (contiene el resultado completo)
    """
    import asyncio
    import json

    if body.horizon not in state.predictor.horizons:
        raise HTTPException(
            status_code=400,
            detail=(
                f"horizonte '{body.horizon}' no soportado; "
                f"disponibles: {', '.join(state.predictor.horizons)}"
            ),
        )

    events_queue: asyncio.Queue[str] = asyncio.Queue()

    async def emit_progress(status: str, data: dict[str, Any]) -> None:
        """Emite un evento SSE a la cola."""
        event = f"event: {status}\ndata: {json.dumps(data)}\n\n"
        await events_queue.put(event)

    async def run_prediction() -> None:
        """Ejecuta la predicción en background y emite eventos."""
        try:
            result = await state.predictor.predict(
                body.query,
                body.horizon,
                sector=body.sector,
                on_progress=emit_progress,
            )
            umbral = (
                body.min_confidence
                if body.min_confidence is not None
                else state.predictor.confidence_min
            )
            result["meets_threshold"] = result["confidence"] >= umbral
            result["threshold"] = umbral
            result["timestamp"] = utcnow().isoformat()
            await emit_progress("result", result)
        except Exception as exc:
            logger.exception("Error en predicción streaming")
            await emit_progress("error", {"message": str(exc)})
        finally:
            await events_queue.put(None)  # Señal de fin

    async def event_generator() -> Any:
        """Generador de eventos SSE."""
        task = asyncio.create_task(run_prediction())

        try:
            while True:
                event = await events_queue.get()
                if event is None:
                    break
                yield event
        finally:
            await task

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@protected.post("/chat", summary="Conversación con un solo agente")
async def chat(body: ChatRequest, state: State) -> dict[str, Any]:
    nombre = body.resolved_agent()
    agente = next((a for a in state.swarm.agents if a.name == nombre), None)
    if agente is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"no existe el agente '{nombre}'; "
                f"disponibles: {', '.join(a.name for a in state.swarm.agents)}"
            ),
        )

    events = await run_in_threadpool(recent_events, limit=15)
    verdict = await agente.analyze(body.query, {"events": events})

    return {
        "agent": agente.name,
        "role": agente.role,
        "response": verdict.prediction,
        "confidence": verdict.confidence,
        "reasoning": verdict.reasoning,
        "sources": verdict.sources_used,
        "timestamp": utcnow().isoformat(),
    }


@protected.post("/whatif", summary="Escenario hipotético")
async def whatif(body: WhatIfRequest, state: State) -> dict[str, Any]:
    """Somete un escenario contrafactual al enjambre, sin persistirlo.

    No se guarda porque no es una predicción sobre el mundo real: no tiene
    desenlace que resolver y contaminaría el Brier score de los agentes.
    """
    pregunta = f"Escenario hipotético: {body.scenario}."
    if body.context:
        pregunta += f" Contexto adicional: {body.context}."
    pregunta += " ¿Qué consecuencias tendría y con qué probabilidad?"

    events = await run_in_threadpool(recent_events, limit=20)
    consensus = await state.swarm.run(pregunta, {"events": events}, horizon=body.horizon)

    return {
        "scenario": body.scenario,
        "horizon": body.horizon,
        "predicted_outcome": consensus.prediction,
        "confidence": consensus.confidence,
        "dissent": consensus.dissent,
        "agent_votes": consensus.agent_votes,
        "reasoning": consensus.reasoning,
        "sources_used": consensus.sources_used,
        "persisted": False,
        "timestamp": utcnow().isoformat(),
    }


# ---------------------------------------------------------------------
# 7-8. Histórico y calibración
# ---------------------------------------------------------------------


@protected.get("/predictions", summary="Predicciones emitidas")
async def list_predictions(
    horizon: str | None = None,
    min_probability: Annotated[float, Query(ge=0.0, le=1.0)] = 0.0,
    resolved: bool | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 10,
) -> dict[str, Any]:
    def query() -> tuple[list[dict[str, Any]], int]:
        with session_scope() as session:
            stmt = select(Prediction).where(Prediction.probability >= min_probability)
            if horizon:
                stmt = stmt.where(Prediction.horizon == horizon)
            if resolved is not None:
                stmt = stmt.where(Prediction.resolved.is_(resolved))

            total = len(session.scalars(stmt).all())
            rows = session.scalars(
                stmt.order_by(Prediction.created_at.desc()).limit(limit)
            ).all()

            return [
                {
                    "id": row.id,
                    "query": row.query_text,
                    "horizon": row.horizon,
                    "prediction": row.prediction_text,
                    "probability": row.probability,
                    "agent_votes": row.agent_votes,
                    "sources_used": row.sources_used,
                    "created_at": row.created_at.isoformat(),
                    "resolved": row.resolved,
                    "actual_outcome": row.actual_outcome,
                    "brier_score": row.brier_score,
                }
                for row in rows
            ], total

    predictions, total = await run_in_threadpool(query)
    return {"predictions": predictions, "total": total, "limit": limit}


@protected.get("/scorecard", summary="Calibración de los agentes")
async def scorecard(
    state: State,
    agent: str | None = None,
    days: Annotated[int, Query(ge=1, le=3650)] = 30,
) -> dict[str, Any]:
    """Brier score y calibración por agente.

    Recordatorio de lectura: **en Brier, más bajo es mejor**. 0 es perfecto,
    0.25 es lo que saca quien siempre responde 0.5, y 1 es lo peor posible.
    """
    from datetime import timedelta

    desde = utcnow() - timedelta(days=days)

    def query() -> list[Prediction]:
        with session_scope() as session:
            return list(
                session.scalars(
                    select(Prediction).where(Prediction.resolved.is_(True))
                ).all()
            )

    resueltas = [
        row
        for row in await run_in_threadpool(query)
        if (row.resolution_time or row.created_at).replace(tzinfo=desde.tzinfo) >= desde
    ]

    agentes = state.swarm.agents
    if agent is not None:
        agentes = [a for a in agentes if a.name == agent]
        if not agentes:
            raise HTTPException(status_code=404, detail=f"no existe el agente '{agent}'")

    salida = {}
    for a in agentes:
        pares = [
            (float(row.agent_votes[a.name]), float(row.outcome_value))
            for row in resueltas
            if row.agent_votes and a.name in row.agent_votes and row.outcome_value is not None
        ]
        cal = calibration(pares)
        salida[a.name] = {
            "role": a.role,
            "brier_score": round(a.brier_score, 4),
            "brier_note": "0 es perfecto, 0.25 equivale a no saber nada, 1 es el peor",
            "weight": round(a.weight, 4),
            "predictions_made": a.predictions_made,
            "resolved_in_period": len(pares),
            "accuracy": round(a.accuracy, 4),
            "confidence_calibration": {
                "avg_predicted_confidence": cal.avg_predicted_confidence,
                "actual_accuracy": cal.actual_accuracy,
                "calibration_ratio": cal.calibration_ratio,
                "reading": _calibration_reading(cal.calibration_ratio),
            },
        }

    return {
        "period_days": days,
        "resolved_predictions": len(resueltas),
        "agents": salida,
        "swarm": build_agent_context(state.swarm.agents),
    }


def _calibration_reading(ratio: float) -> str:
    if ratio == 0.0:
        return "sin datos suficientes"
    if ratio > 1.1:
        return "exceso de confianza"
    if ratio < 0.9:
        return "prudencia excesiva"
    return "bien calibrado"


# ---------------------------------------------------------------------
# 9. Flujo en tiempo real
# ---------------------------------------------------------------------


@protected.get("/state/stream", summary="Flujo de estado (SSE)")
async def stream(
    state: State,
    interval: Annotated[int, Query(ge=1, le=300)] = 30,
) -> Any:
    return state_stream(state, interval)


@protected.post("/feeds/refresh", summary="Fuerza una ronda de ingesta")
async def refresh_feeds(state: State) -> dict[str, Any]:
    report = await state.ingestor.run_once()
    return report.to_dict()


router.include_router(protected)


__all__ = ["router"]
