"""Los siete agentes del enjambre MiroFish."""

from __future__ import annotations

from engine.llm.ollama_client import LLMClient
from engine.mirofish.agents.base import Agent
from engine.mirofish.agents.climate_expert import ClimateExpert
from engine.mirofish.agents.economist import Economist
from engine.mirofish.agents.geopolitical import GeopoliticalRisk
from engine.mirofish.agents.naturalist import Naturalist
from engine.mirofish.agents.skeptic import Skeptic
from engine.mirofish.agents.strategist import Strategist
from engine.mirofish.agents.tech_analyst import TechAnalyst

# El orden importa: es el que ve el modelo en el prompt y el que aparece en la UI.
AGENT_CLASSES: tuple[type[Agent], ...] = (
    Strategist,
    Economist,
    Skeptic,
    Naturalist,
    TechAnalyst,
    ClimateExpert,
    GeopoliticalRisk,
)


def build_agents(llm: LLMClient | None = None, limit: int | None = None) -> list[Agent]:
    """Instancia el enjambre.

    `limit` recorta el número de agentes (`MIROFISH_AGENTS`), útil para reducir
    la longitud del prompt en máquinas apuradas de memoria.
    """
    classes = AGENT_CLASSES if limit is None else AGENT_CLASSES[:limit]
    return [cls(llm=llm) for cls in classes]


__all__ = [
    "AGENT_CLASSES",
    "Agent",
    "ClimateExpert",
    "Economist",
    "GeopoliticalRisk",
    "Naturalist",
    "Skeptic",
    "Strategist",
    "TechAnalyst",
    "build_agents",
]
