"""Contrato JSON con el modelo, y su tolerancia a fallos.

Un LLM de 7B cuantizado no siempre devuelve JSON limpio ni siquiera con
`format: "json"`: envuelve la respuesta en vallas de código, la precede de
prosa o corta por el final. `extract_json` absorbe esos casos; lo que no
absorbe se convierte en un reintento en el enjambre.
"""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, Field, field_validator

_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


class MalformedResponseError(ValueError):
    """El modelo no devolvió un JSON aprovechable."""


def extract_json(raw: str) -> dict[str, Any]:
    """Saca el primer objeto JSON de la respuesta del modelo."""
    text = raw.strip()

    fenced = _FENCE.search(text)
    if fenced:
        text = fenced.group(1).strip()

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        # Segundo intento: recortar desde la primera llave hasta la última.
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            raise MalformedResponseError(f"No hay ningún objeto JSON en: {raw[:200]!r}") from None
        try:
            parsed = json.loads(text[start : end + 1])
        except json.JSONDecodeError as exc:
            raise MalformedResponseError(f"JSON inválido: {exc}") from exc

    if not isinstance(parsed, dict):
        raise MalformedResponseError(f"Se esperaba un objeto JSON, llegó {type(parsed).__name__}")
    return parsed


class AgentVerdict(BaseModel):
    """Dictamen de un agente sobre la pregunta planteada."""

    prediction: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str = ""
    sources_used: list[str] = Field(default_factory=list)

    @field_validator("confidence", mode="before")
    @classmethod
    def _coerce_confidence(cls, value: Any) -> Any:
        """Acepta `"0.78"`, `78` y `78%`; todo acaba en la escala 0-1.

        Los modelos pequeños confunden porcentaje con probabilidad a menudo.
        """
        if isinstance(value, str):
            value = value.strip().rstrip("%")
            try:
                value = float(value)
            except ValueError:
                return value
        if isinstance(value, (int, float)) and 1 < value <= 100:
            return value / 100
        return value

    @field_validator("sources_used", mode="before")
    @classmethod
    def _coerce_sources(cls, value: Any) -> Any:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


class SwarmResponse(BaseModel):
    """Respuesta completa del prompt multi-persona."""

    verdicts: dict[str, AgentVerdict]
    synthesis: str = ""

    @field_validator("verdicts")
    @classmethod
    def _not_empty(cls, value: dict[str, AgentVerdict]) -> dict[str, AgentVerdict]:
        if not value:
            raise ValueError("el modelo no emitió ningún dictamen")
        return value
