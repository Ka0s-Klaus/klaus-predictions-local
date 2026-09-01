"""Construcción de prompts.

Dos formas de preguntar:

- `build_swarm_prompt` — una única llamada en la que el modelo encarna a los
  siete agentes y devuelve los siete dictámenes de golpe. Es lo que usa
  `/predict`. Siete llamadas independientes a un 7B cuantizado en CPU serían
  minutos por predicción; ésta es la razón de que exista este formato.
- `build_agent_prompt` — un solo agente, para `/chat`.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from engine.mirofish.agents.base import Agent

SYSTEM_PROMPT = (
    "Eres el motor de razonamiento de Pythia, un oráculo de predicción que opera "
    "sobre señales del mundo real. Respondes SIEMPRE con JSON válido y nada más: "
    "sin texto introductorio, sin vallas de código, sin comentarios. "
    "Calibras tu confianza con honestidad: si la evidencia es débil, la confianza "
    "es baja. Nunca inventas fuentes que no aparezcan en el contexto."
)

_MAX_EVENTS = 25
_MAX_TITLE = 160


def format_events(events: Sequence[dict[str, Any]], limit: int = _MAX_EVENTS) -> str:
    """Resume los eventos de los feeds en líneas cortas.

    El contexto por defecto es de 4096 tokens y hay que dejar sitio para siete
    dictámenes, así que aquí se recorta con mano dura.
    """
    if not events:
        return "(sin eventos recientes; razona a partir de conocimiento general y dilo)"

    lines = []
    for event in events[:limit]:
        source = event.get("source", "?")
        title = str(event.get("title") or event.get("description") or "").strip()
        if len(title) > _MAX_TITLE:
            title = title[: _MAX_TITLE - 1] + "…"
        salience = event.get("salience")
        marker = f" [rel={salience:.2f}]" if isinstance(salience, (int, float)) else ""
        lines.append(f"- [{source}]{marker} {title}")
    return "\n".join(lines)


def _agent_roster(agents: Sequence[Agent]) -> str:
    return "\n".join(
        f"- {agent.name} ({agent.role}): {agent.persona} "
        f"Dominios: {', '.join(agent.domains)}."
        for agent in agents
    )


def build_swarm_prompt(
    query: str,
    agents: Sequence[Agent],
    events: Sequence[dict[str, Any]],
    horizon: str,
    *,
    error_hint: str | None = None,
) -> str:
    """Prompt multi-persona. `error_hint` se usa en el reintento tras un JSON malo."""
    names = [agent.name for agent in agents]
    schema_keys = ",\n".join(
        f'    "{name}": {{"prediction": "…", "confidence": 0.0, '
        f'"reasoning": "…", "sources_used": ["…"]}}'
        for name in names
    )

    retry_block = ""
    if error_hint:
        retry_block = (
            "\nTu respuesta anterior no se pudo procesar. Motivo exacto: "
            f"{error_hint}\nDevuelve SOLO el objeto JSON, sin nada alrededor.\n"
        )

    return f"""Pregunta: {query}
Horizonte de predicción: {horizon}

Señales recientes de los feeds:
{format_events(events)}

Actúa como los {len(agents)} analistas siguientes. Cada uno responde desde su
especialidad y puede discrepar de los demás; discrepar es útil, no lo evites.

{_agent_roster(agents)}

Reglas:
- `confidence` es una probabilidad entre 0 y 1, no un porcentaje.
- `sources_used` sólo puede contener fuentes que aparezcan arriba.
- `reasoning` va en dos frases como mucho.
- `synthesis` resume en qué coinciden y en qué chocan los analistas.
{retry_block}
Responde exactamente con esta forma:
{{
  "verdicts": {{
{schema_keys}
  }},
  "synthesis": "…"
}}"""


def build_agent_prompt(
    agent: Agent,
    query: str,
    events: Sequence[dict[str, Any]],
    *,
    error_hint: str | None = None,
) -> str:
    """Prompt de un solo agente, para conversación directa."""
    retry_block = ""
    if error_hint:
        retry_block = f"\nTu respuesta anterior falló: {error_hint}. Devuelve SOLO el JSON.\n"

    return f"""Eres {agent.name}, {agent.role}.
{agent.persona}
Dominios que cubres: {', '.join(agent.domains)}.

Pregunta: {query}

Señales recientes de los feeds:
{format_events(events)}

Reglas:
- `confidence` es una probabilidad entre 0 y 1, no un porcentaje.
- `sources_used` sólo puede contener fuentes que aparezcan arriba.
{retry_block}
Responde exactamente con esta forma:
{{"prediction": "…", "confidence": 0.0, "reasoning": "…", "sources_used": ["…"]}}"""
