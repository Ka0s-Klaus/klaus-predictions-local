"""Pythia — oráculo de predicción local-first.

Ingesta feeds públicos, los resume con un LLM que corre en la propia máquina y
somete cada pregunta a un enjambre de agentes cuyos votos se ponderan por su
historial de acierto (Brier score).
"""

__version__ = "0.1.0"

__all__ = ["__version__"]
