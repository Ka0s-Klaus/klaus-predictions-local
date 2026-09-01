"""Dobles de prueba y datos de ejemplo.

Requisito duro de la suite: pasa **sin red, sin Ollama y sin PostgreSQL**.
Todo lo que saldría de la máquina se sustituye aquí.
"""

from __future__ import annotations

import json
from typing import Any

AGENT_NAMES = (
    "Strategist",
    "Economist",
    "Skeptic",
    "Naturalist",
    "Tech_Analyst",
    "Climate_Expert",
    "Geopolitical",
)

SAMPLE_EVENTS: list[dict[str, Any]] = [
    {
        "source": "USGS",
        "event_type": "earthquake",
        "title": "M 6.1 - 120 km SE of Tokyo, Japan",
        "salience": 0.82,
        "latitude": 35.1,
        "longitude": 140.9,
    },
    {
        "source": "CAISO",
        "event_type": "energy",
        "title": "Operating reserves below 6% during evening ramp",
        "salience": 0.74,
    },
    {
        "source": "GDELT",
        "event_type": "political",
        "title": "Trade delegation talks suspended without joint statement",
        "salience": 0.66,
    },
]


def swarm_payload(
    confidences: dict[str, float] | None = None,
    *,
    synthesis: str = "Riesgo sísmico elevado con tensión de red correlacionada.",
    wrap: bool = True,
) -> str:
    """Respuesta bien formada del prompt multi-persona."""
    confidences = confidences or dict.fromkeys(AGENT_NAMES, 0.7)
    verdicts = {
        name: {
            "prediction": f"Valoración de {name}.",
            "confidence": value,
            "reasoning": f"{name} razona sobre las señales disponibles.",
            "sources_used": ["USGS", "CAISO"],
        }
        for name, value in confidences.items()
    }
    payload = {"verdicts": verdicts, "synthesis": synthesis} if wrap else verdicts
    return json.dumps(payload, ensure_ascii=False)


def agent_payload(confidence: float = 0.72) -> str:
    """Respuesta bien formada de un único agente."""
    return json.dumps(
        {
            "prediction": "La red aguanta el pico vespertino.",
            "confidence": confidence,
            "reasoning": "Las reservas siguen por encima del umbral crítico.",
            "sources_used": ["CAISO"],
        }
    )


class FakeLLM:
    """Cliente LLM programable. Cumple el `Protocol` de `engine.llm.LLMClient`."""

    def __init__(self, responses: list[str] | str) -> None:
        self.responses = [responses] if isinstance(responses, str) else list(responses)
        self.calls: list[dict[str, Any]] = []

    async def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        json_mode: bool = False,
        max_tokens: int | None = None,
    ) -> str:
        self.calls.append(
            {
                "prompt": prompt,
                "system": system,
                "json_mode": json_mode,
                "max_tokens": max_tokens,
            }
        )
        if not self.responses:
            raise AssertionError("FakeLLM se quedó sin respuestas programadas")
        # La última respuesta se repite para no obligar a contar llamadas exactas.
        return self.responses.pop(0) if len(self.responses) > 1 else self.responses[0]

    @property
    def call_count(self) -> int:
        return len(self.calls)
