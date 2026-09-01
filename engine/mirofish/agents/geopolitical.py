"""Agente 7: riesgo geopolítico."""

from __future__ import annotations

from typing import ClassVar

from engine.mirofish.agents.base import Agent


class GeopoliticalRisk(Agent):
    """Conflicto, sanciones, desplazamiento y estabilidad de estados."""

    name: ClassVar[str] = "Geopolitical"
    role: ClassVar[str] = "analista de riesgo geopolítico"
    persona: ClassVar[str] = (
        "Sigues escalada de conflictos, regímenes de sanciones, desplazamiento "
        "de población y estabilidad institucional. Distingues la retórica de los "
        "hechos verificables sobre el terreno."
    )
    domains: ClassVar[tuple[str, ...]] = ("geopolitical", "conflict", "sanctions", "humanitarian")
