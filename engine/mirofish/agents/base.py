"""Clase base de los agentes MiroFish.

Un agente es tres cosas: una identidad (nombre, rol, persona, dominios), un
historial de acierto que pondera su voto, y la capacidad de emitir un dictamen
por su cuenta cuando se le pregunta directamente.

En `/predict` los siete agentes se resuelven en una única llamada al modelo
(ver `engine.llm.prompts.build_swarm_prompt`); `analyze()` es el camino de un
solo agente que usa `/chat`.
"""

from __future__ import annotations

from typing import Any, ClassVar

from engine.llm.ollama_client import LLMClient
from engine.llm.schemas import AgentVerdict, MalformedResponseError, extract_json

# Un agente sin historial arranca aquí: es lo que puntúa quien siempre dice 0.5.
NEUTRAL_BRIER = 0.25

# Por debajo de este error absoluto se cuenta la predicción como acertada.
CORRECTNESS_MARGIN = 0.5


class Agent:
    """Analista especializado con historial de calibración.

    No se instancia directamente: cada subclase aporta su `persona`, que es lo
    que la diferencia dentro del prompt.
    """

    name: ClassVar[str] = "Agent"
    role: ClassVar[str] = "analista"
    persona: ClassVar[str] = ""
    domains: ClassVar[tuple[str, ...]] = ()

    def __init__(
        self,
        llm: LLMClient | None = None,
        *,
        brier_score: float = NEUTRAL_BRIER,
        predictions_made: int = 0,
        correct_predictions: int = 0,
    ) -> None:
        if not self.persona:
            raise TypeError(
                f"{type(self).__name__} no define `persona`. Sin ella el agente es "
                "indistinguible del resto dentro del prompt."
            )
        self.llm = llm
        self.brier_score = brier_score
        self.predictions_made = predictions_made
        self.correct_predictions = correct_predictions

    def __repr__(self) -> str:
        return f"<{type(self).__name__} brier={self.brier_score:.3f} n={self.predictions_made}>"

    # ------------------------------------------------------------------
    # Calibración
    # ------------------------------------------------------------------

    @property
    def weight(self) -> float:
        """Peso del voto. Mejor Brier (más bajo) pesa más."""
        return 1.0 / (1.0 + max(self.brier_score, 0.0))

    @property
    def accuracy(self) -> float:
        if self.predictions_made == 0:
            return 0.0
        return self.correct_predictions / self.predictions_made

    def update_brier_score(self, prediction: float, actual: float) -> float:
        """Incorpora un desenlace al historial y devuelve el Brier de esta predicción.

        La especificación original actualizaba la media pero nunca tocaba
        `correct_predictions`, con lo que la precisión se quedaba clavada en cero.
        """
        squared_error = (prediction - actual) ** 2
        total = self.brier_score * self.predictions_made + squared_error
        self.predictions_made += 1
        self.brier_score = total / self.predictions_made
        if abs(prediction - actual) < CORRECTNESS_MARGIN:
            self.correct_predictions += 1
        return squared_error

    # ------------------------------------------------------------------
    # Razonamiento individual
    # ------------------------------------------------------------------

    async def analyze(self, query: str, context: dict[str, Any] | None = None) -> AgentVerdict:
        """Consulta al modelo desde la perspectiva de este agente.

        Un reintento si el JSON viene mal; a la segunda, propaga el error.
        """
        if self.llm is None:
            raise RuntimeError(
                f"{self.name} no tiene cliente LLM. Pásalo al construir el agente."
            )

        # Import local: `prompts` importa `Agent` sólo para anotaciones de tipo.
        from engine.llm.prompts import SYSTEM_PROMPT, build_agent_prompt

        events = (context or {}).get("events", [])
        error_hint: str | None = None

        for attempt in (1, 2):
            prompt = build_agent_prompt(self, query, events, error_hint=error_hint)
            raw = await self.llm.generate(prompt, system=SYSTEM_PROMPT, json_mode=True)
            try:
                return AgentVerdict.model_validate(extract_json(raw))
            except (MalformedResponseError, ValueError) as exc:
                if attempt == 2:
                    raise MalformedResponseError(
                        f"{self.name} devolvió JSON inaprovechable dos veces: {exc}"
                    ) from exc
                error_hint = str(exc)[:200]

        raise AssertionError("inalcanzable")  # pragma: no cover

    async def vote(self, proposal: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        """Voto del agente sobre una propuesta concreta."""
        verdict = await self.analyze(proposal, context)
        return {
            "agent": self.name,
            "vote": verdict.confidence,
            "reasoning": verdict.reasoning,
        }
