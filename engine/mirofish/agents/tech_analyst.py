"""Agente 5: análisis tecnológico."""

from __future__ import annotations

from typing import ClassVar

from engine.mirofish.agents.base import Agent


class TechAnalyst(Agent):
    """Infraestructura digital, ciberseguridad y cortes de red."""

    name: ClassVar[str] = "Tech_Analyst"
    role: ClassVar[str] = "analista tecnológico"
    persona: ClassVar[str] = (
        "Cubres vulnerabilidades explotadas, cortes de conectividad y fragilidad "
        "de la infraestructura digital. Te fijas en dependencias compartidas: un "
        "único proveedor caído puede arrastrar sectores enteros."
    )
    domains: ClassVar[tuple[str, ...]] = ("cyber", "infrastructure", "outages", "technology")
