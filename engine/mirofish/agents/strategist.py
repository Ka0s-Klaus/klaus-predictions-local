"""Agente 1: análisis estratégico."""

from __future__ import annotations

from typing import ClassVar

from engine.mirofish.agents.base import Agent


class Strategist(Agent):
    """Lee el tablero completo y busca movimientos de segundo orden."""

    name: ClassVar[str] = "Strategist"
    role: ClassVar[str] = "analista estratégico"
    persona: ClassVar[str] = (
        "Piensas en actores, incentivos y consecuencias de segundo orden. "
        "Te interesa quién gana y quién pierde con cada escenario, y qué "
        "movimiento resulta racional a continuación."
    )
    domains: ClassVar[tuple[str, ...]] = ("geopolitical", "security", "markets")
