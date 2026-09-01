"""Consenso ponderado por Brier score.

La idea que se conserva íntegra de la especificación: el voto de cada agente
pesa `1 / (1 + brier)`, de modo que quien acierta más históricamente inclina
más la balanza. Un agente sin historial parte de un Brier neutro de 0.25.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from engine.llm.schemas import AgentVerdict
from engine.mirofish.agents.base import Agent


@dataclass(frozen=True)
class ConsensusResult:
    """Resultado agregado del enjambre."""

    prediction: str
    confidence: float
    reasoning: str
    agent_votes: dict[str, float]
    weights: dict[str, float]
    sources_used: list[str] = field(default_factory=list)
    dissent: float = 0.0
    """Desviación típica de las confianzas. Alta = el enjambre no se pone de acuerdo."""

    @property
    def is_actionable(self) -> bool:
        """Sólo informativo; el umbral lo aplica quien consume el resultado."""
        return self.confidence > 0.0


def _stddev(values: Sequence[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    return variance**0.5


def weighted_consensus(
    verdicts: Mapping[str, AgentVerdict],
    agents: Sequence[Agent],
    *,
    synthesis: str = "",
    brier_weighted: bool = True,
) -> ConsensusResult:
    """Combina los dictámenes en una única predicción.

    Sólo se tienen en cuenta los agentes que efectivamente votaron: si el modelo
    omite uno, su peso no debe seguir contando en el denominador.
    """
    by_name = {agent.name: agent for agent in agents}

    weights = {
        name: (by_name[name].weight if brier_weighted else 1.0)
        for name in verdicts
        if name in by_name
    }
    if not weights:
        raise ValueError(
            f"Ningún dictamen corresponde a un agente conocido. "
            f"Recibidos: {sorted(verdicts)}; esperados: {sorted(by_name)}"
        )

    total_weight = sum(weights.values())
    confidence = sum(verdicts[name].confidence * w for name, w in weights.items()) / total_weight

    agent_votes = {name: round(verdicts[name].confidence, 4) for name in weights}

    sources: list[str] = []
    for name in weights:
        for source in verdicts[name].sources_used:
            if source not in sources:
                sources.append(source)

    if synthesis.strip():
        prediction = synthesis.strip()
    else:
        # Sin síntesis del modelo, gana el dictamen del agente de mayor peso
        # efectivo (peso histórico por su propia confianza).
        leader = max(weights, key=lambda n: weights[n] * verdicts[n].confidence)
        prediction = verdicts[leader].prediction

    reasoning = "\n".join(
        f"{name} ({verdicts[name].confidence:.2f}, peso {weights[name]:.2f}): "
        f"{verdicts[name].reasoning or verdicts[name].prediction}"
        for name in weights
    )

    return ConsensusResult(
        prediction=prediction,
        confidence=round(confidence, 4),
        reasoning=reasoning,
        agent_votes=agent_votes,
        weights={name: round(w, 4) for name, w in weights.items()},
        sources_used=sources,
        dissent=round(_stddev([verdicts[n].confidence for n in weights]), 4),
    )
