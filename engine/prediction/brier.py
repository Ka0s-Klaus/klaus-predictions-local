"""Brier score y calibración.

El Brier score es el error cuadrático medio de una probabilidad frente al
desenlace binario: **0 es perfecto, 1 es lo peor posible, 0.25 es lo que saca
quien siempre dice 0.5**. Conviene recordarlo porque la especificación original
mostraba `"brier_score": 0.68` junto a `"accuracy": 0.79`, y esas dos cifras no
pueden convivir: 0.68 es peor que no tener ni idea.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

# Brier de un pronosticador que siempre responde 0.5.
UNINFORMED_BRIER = 0.25


def brier_score(probability: float, outcome: float) -> float:
    """Error cuadrático de una única predicción. `outcome` es 1.0 o 0.0."""
    if not 0.0 <= probability <= 1.0:
        raise ValueError(f"la probabilidad debe estar entre 0 y 1, llegó {probability}")
    if not 0.0 <= outcome <= 1.0:
        raise ValueError(f"el desenlace debe estar entre 0 y 1, llegó {outcome}")
    return (probability - outcome) ** 2


def mean_brier(pairs: Sequence[tuple[float, float]]) -> float:
    """Brier medio de una serie de pares `(probabilidad, desenlace)`."""
    if not pairs:
        return UNINFORMED_BRIER
    return sum(brier_score(p, o) for p, o in pairs) / len(pairs)


def brier_skill_score(pairs: Sequence[tuple[float, float]]) -> float:
    """Mejora relativa frente a decir siempre 0.5.

    Positivo = aporta información. Cero = da igual. Negativo = peor que nada.
    """
    if not pairs:
        return 0.0
    return 1.0 - mean_brier(pairs) / UNINFORMED_BRIER


def running_update(current: float, count: int, probability: float, outcome: float) -> float:
    """Media incremental del Brier, sin recorrer el histórico."""
    score = brier_score(probability, outcome)
    return (current * count + score) / (count + 1)


@dataclass(frozen=True)
class Calibration:
    """Confianza declarada frente a acierto real."""

    avg_predicted_confidence: float
    actual_accuracy: float
    sample_size: int

    @property
    def calibration_ratio(self) -> float:
        """>1 significa exceso de confianza; <1, prudencia excesiva."""
        if self.actual_accuracy == 0.0:
            return 0.0
        return round(self.avg_predicted_confidence / self.actual_accuracy, 4)


def calibration(pairs: Sequence[tuple[float, float]], margin: float = 0.5) -> Calibration:
    """Compara la confianza media con la tasa de acierto observada."""
    if not pairs:
        return Calibration(0.0, 0.0, 0)
    avg_confidence = sum(p for p, _ in pairs) / len(pairs)
    hits = sum(1 for p, o in pairs if abs(p - o) < margin)
    return Calibration(
        avg_predicted_confidence=round(avg_confidence, 4),
        actual_accuracy=round(hits / len(pairs), 4),
        sample_size=len(pairs),
    )
