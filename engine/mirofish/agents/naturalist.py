"""Agente 4: fenómenos naturales."""

from __future__ import annotations

from typing import ClassVar

from engine.mirofish.agents.base import Agent


class Naturalist(Agent):
    """Terremotos, volcanes, incendios, inundaciones y tormentas."""

    name: ClassVar[str] = "Naturalist"
    role: ClassVar[str] = "analista de fenómenos naturales"
    persona: ClassVar[str] = (
        "Interpretas eventos sísmicos, volcánicos, hidrológicos y de incendio. "
        "Distingues la magnitud física del impacto humano: un terremoto grande "
        "lejos de todo importa menos que uno moderado bajo una ciudad."
    )
    domains: ClassVar[tuple[str, ...]] = ("disasters", "seismic", "wildfire", "flood")
