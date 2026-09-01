"""Agente 6: clima y medio ambiente."""

from __future__ import annotations

from typing import ClassVar

from engine.mirofish.agents.base import Agent


class ClimateExpert(Agent):
    """Escalas largas: estacionalidad, oscilaciones y clima espacial."""

    name: ClassVar[str] = "Climate_Expert"
    role: ClassVar[str] = "experto en clima"
    persona: ClassVar[str] = (
        "Trabajas en escalas de semanas a años: anomalías estacionales, ENSO, "
        "clima espacial y su efecto sobre energía, agricultura y transporte. "
        "Separas la señal climática de la meteorología de un día."
    )
    domains: ClassVar[tuple[str, ...]] = ("climate", "weather", "space-weather", "agriculture")
