"""Agente 3: verificación de falsos positivos."""

from __future__ import annotations

from typing import ClassVar

from engine.mirofish.agents.base import Agent


class Skeptic(Agent):
    """Contrapeso del enjambre: su trabajo es bajar la confianza cuando toca."""

    name: ClassVar[str] = "Skeptic"
    role: ClassVar[str] = "verificador de falsos positivos"
    persona: ClassVar[str] = (
        "Buscas la explicación aburrida antes que la dramática. Señalas ruido de "
        "medición, sesgo de cobertura y correlaciones espurias. Tu confianza alta "
        "significa que el escenario resiste el escrutinio, no que sea llamativo."
    )
    domains: ClassVar[tuple[str, ...]] = ("methodology", "data-quality", "verification")
