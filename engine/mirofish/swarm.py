"""Orquestador del enjambre MiroFish.

Los siete agentes se resuelven en **una sola llamada al modelo**. La
especificación describía siete llamadas "en paralelo", pero contra un Mistral 7B
cuantizado sobre CPU las llamadas se serializan en el propio Ollama: a 2-4
tokens/s y 384 tokens por agente son minutos por predicción. Un prompt
multi-persona baja eso a una sola generación manteniendo los siete roles y el
voto ponderado.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any

from engine.llm.ollama_client import LLMClient
from engine.llm.prompts import SYSTEM_PROMPT, build_swarm_prompt
from engine.llm.schemas import AgentVerdict, MalformedResponseError, SwarmResponse, extract_json
from engine.mirofish.agents.base import Agent
from engine.mirofish.consensus import ConsensusResult, weighted_consensus

logger = logging.getLogger(__name__)

# Con siete dictámenes en un solo JSON, el techo por defecto de 384 tokens se
# queda corto y la respuesta se trunca a media llave.
TOKENS_PER_AGENT = 130
MIN_SWARM_TOKENS = 512


class SwarmError(RuntimeError):
    """El enjambre no pudo producir un consenso."""


class MiroFishSwarm:
    """Somete una pregunta a los agentes y agrega sus votos."""

    def __init__(
        self,
        agents: Sequence[Agent],
        llm: LLMClient,
        *,
        consensus_threshold: float = 0.65,
        brier_weighted: bool = True,
    ) -> None:
        if not agents:
            raise ValueError("el enjambre necesita al menos un agente")
        self.agents = list(agents)
        self.llm = llm
        self.consensus_threshold = consensus_threshold
        self.brier_weighted = brier_weighted

    @property
    def token_budget(self) -> int:
        return max(MIN_SWARM_TOKENS, TOKENS_PER_AGENT * len(self.agents))

    async def run(
        self,
        query: str,
        context: dict[str, Any] | None = None,
        horizon: str = "24h",
    ) -> ConsensusResult:
        """Ejecuta el razonamiento del enjambre.

        Un reintento si el modelo devuelve JSON inservible, incluyéndole el error
        concreto para que se corrija. A la segunda, `SwarmError`.
        """
        events = (context or {}).get("events", [])
        error_hint: str | None = None
        last_error: Exception | None = None

        for attempt in (1, 2):
            prompt = build_swarm_prompt(
                query, self.agents, events, horizon, error_hint=error_hint
            )
            raw = await self.llm.generate(
                prompt,
                system=SYSTEM_PROMPT,
                json_mode=True,
                max_tokens=self.token_budget,
            )
            try:
                response = self._parse(raw)
            except (MalformedResponseError, ValueError) as exc:
                last_error = exc
                error_hint = str(exc)[:200]
                logger.warning("Respuesta del enjambre inválida (intento %d): %s", attempt, exc)
                continue

            return weighted_consensus(
                response.verdicts,
                self.agents,
                synthesis=response.synthesis,
                brier_weighted=self.brier_weighted,
            )

        raise SwarmError(
            f"El modelo no devolvió un JSON válido en dos intentos: {last_error}"
        ) from last_error

    def _parse(self, raw: str) -> SwarmResponse:
        """Valida la respuesta, tolerando que el modelo omita el envoltorio.

        Un 7B a veces devuelve `{"Strategist": {...}, ...}` directamente en lugar
        de `{"verdicts": {...}}`. Se acepta si las claves son nombres de agentes.
        """
        payload = extract_json(raw)

        if "verdicts" not in payload:
            known = {agent.name for agent in self.agents}
            if payload and set(payload) & known:
                payload = {
                    "verdicts": {k: v for k, v in payload.items() if k in known},
                    "synthesis": str(payload.get("synthesis", "")),
                }

        response = SwarmResponse.model_validate(payload)

        unknown = set(response.verdicts) - {agent.name for agent in self.agents}
        if unknown:
            logger.debug("El modelo inventó agentes, se descartan: %s", sorted(unknown))
            response = SwarmResponse(
                verdicts={k: v for k, v in response.verdicts.items() if k not in unknown},
                synthesis=response.synthesis,
            )
        return response

    def record_outcome(self, agent_votes: dict[str, float], actual: float) -> dict[str, float]:
        """Propaga un desenlace a los agentes que votaron. Devuelve el Brier de cada uno."""
        by_name = {agent.name: agent for agent in self.agents}
        scores: dict[str, float] = {}
        for name, vote in agent_votes.items():
            agent = by_name.get(name)
            if agent is not None:
                scores[name] = agent.update_brier_score(vote, actual)
        return scores


__all__ = ["AgentVerdict", "MiroFishSwarm", "SwarmError"]
