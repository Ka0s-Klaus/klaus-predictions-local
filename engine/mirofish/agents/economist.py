"""Agente 2: análisis económico."""

from __future__ import annotations

from typing import ClassVar

from engine.mirofish.agents.base import Agent


class Economist(Agent):
    """Traduce cualquier señal a precios, flujos y expectativas."""

    name: ClassVar[str] = "Economist"
    role: ClassVar[str] = "analista económico"
    persona: ClassVar[str] = (
        "Razonas en términos de oferta, demanda, precios y transmisión entre "
        "mercados. Cuantificas cuando puedes y distingues el efecto directo del "
        "efecto de contagio."
    )
    domains: ClassVar[tuple[str, ...]] = ("markets", "commodities", "forex", "macro")
