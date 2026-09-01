"""Esquema de base de datos (SQLAlchemy 2.0).

Cuatro tablas: eventos ingeridos de los feeds, predicciones emitidas, registro de
auditoría y marcador histórico por agente.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    """Instante actual con zona horaria.

    `datetime.utcnow()` está deprecado desde Python 3.12 y devuelve un naive
    datetime, que se compara mal con los timestamps de los feeds.
    """
    return datetime.now(UTC)


class Base(DeclarativeBase):
    """Base declarativa común."""


class FeedEvent(Base):
    """Un evento normalizado procedente de una fuente externa."""

    __tablename__ = "feed_events"
    __table_args__ = (
        CheckConstraint("latitude IS NULL OR (latitude BETWEEN -90 AND 90)", name="chk_lat"),
        CheckConstraint("longitude IS NULL OR (longitude BETWEEN -180 AND 180)", name="chk_lng"),
        Index("idx_feed_time", "event_time"),
        Index("idx_feed_source_time", "source", "event_time"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(100), index=True)
    event_type: Mapped[str | None] = mapped_column(String(50))
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    magnitude: Mapped[float | None] = mapped_column(Float)
    title: Mapped[str | None] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(String(500))
    salience: Mapped[float] = mapped_column(Float, default=0.5)
    ingestion_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )
    event_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Clave natural para deduplicar reingestas de la misma fuente.
    external_id: Mapped[str | None] = mapped_column(String(255), index=True)
    raw_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class Prediction(Base):
    """Una predicción emitida por el enjambre, con su resolución posterior."""

    __tablename__ = "predictions"
    __table_args__ = (
        CheckConstraint("probability BETWEEN 0 AND 1", name="chk_probability"),
        Index("idx_pred_horizon_created", "horizon", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    query_text: Mapped[str] = mapped_column(Text)
    sector: Mapped[str | None] = mapped_column(String(100))
    horizon: Mapped[str] = mapped_column(String(20), index=True)
    prediction_text: Mapped[str] = mapped_column(Text)
    probability: Mapped[float] = mapped_column(Float)
    agent_votes: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    reasoning: Mapped[str | None] = mapped_column(Text)
    sources_used: Mapped[list[str] | None] = mapped_column(JSON)
    latency_ms: Mapped[int | None] = mapped_column(Integer)

    # Resolución: se rellenan cuando el horizonte vence y se conoce el desenlace.
    resolved: Mapped[bool] = mapped_column(default=False, index=True)
    actual_outcome: Mapped[str | None] = mapped_column(Text)
    outcome_value: Mapped[float | None] = mapped_column(Float)
    brier_score: Mapped[float | None] = mapped_column(Float)
    resolution_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class AuditLog(Base):
    """Traza de operaciones para depuración y análisis de latencia."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_type: Mapped[str] = mapped_column(String(100), index=True)
    agent_id: Mapped[str | None] = mapped_column(String(255))
    action: Mapped[str | None] = mapped_column(String(500))
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )


class AgentScore(Base):
    """Marcador acumulado de un agente: es lo que pondera su voto."""

    __tablename__ = "agent_scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    agent_name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    # Brier score medio: 0 es perfecto, 1 es el peor posible. Un agente sin
    # historial arranca en 0.25, que es lo que puntúa predecir siempre 0.5.
    brier_score: Mapped[float] = mapped_column(Float, default=0.25)
    predictions_made: Mapped[int] = mapped_column(Integer, default=0)
    correct_predictions: Mapped[int] = mapped_column(Integer, default=0)
    accuracy: Mapped[float] = mapped_column(Float, default=0.0)
    avg_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


# Brier de partida de un agente sin historial: lo que puntúa decir siempre 0.5.
NEUTRAL_BRIER = 0.25


def new_agent_score(agent_name: str) -> AgentScore:
    """Marcador recién creado, con los contadores ya inicializados.

    Los `default=` de las columnas sólo se aplican al hacer el `INSERT`. Hasta
    ese momento los atributos valen `None`, y cualquier aritmética sobre ellos
    revienta antes de llegar al flush.
    """
    return AgentScore(
        agent_name=agent_name,
        brier_score=NEUTRAL_BRIER,
        predictions_made=0,
        correct_predictions=0,
        accuracy=0.0,
        avg_confidence=0.0,
    )
