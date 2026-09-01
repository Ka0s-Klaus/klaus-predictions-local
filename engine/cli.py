"""Interfaz de línea de comandos.

    python -m engine.cli predict --query "¿Riesgo de red?" --horizon 24h
    python -m engine.cli world-brief
    python -m engine.cli ingest
    python -m engine.cli status
    python -m engine.cli scorecard
    python -m engine.cli resolve --id 42 --outcome 1
    python -m engine.cli feeds

La especificación no incluía este módulo en su árbol, pero la guía de
instalación lo invoca. Existe por eso.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from typing import Any

from engine import database
from engine.api.app import build_state
from engine.config import get_settings
from engine.feeds import event_counts, implemented_entries, planned_entries, recent_events, summary
from engine.prediction import resolve as resolve_prediction

logger = logging.getLogger(__name__)


def _print(data: Any) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False, default=str))


async def cmd_predict(args: argparse.Namespace) -> int:
    state = build_state()
    state.predictor.load_agent_scores()
    try:
        result = await state.predictor.predict(args.query, args.horizon, sector=args.sector)
    finally:
        await state.llm.close()

    if args.json:
        _print(result)
    else:
        print(f"\n  {result['prediction']}\n")
        print(f"  Confianza: {result['confidence']:.0%}   Discrepancia: {result['dissent']:.3f}")
        print(f"  Latencia:  {result['latency_ms'] / 1000:.1f}s")
        print(f"  Fuentes:   {', '.join(result['sources_used']) or '—'}\n")
        for nombre, voto in sorted(result["agent_votes"].items(), key=lambda kv: -kv[1]):
            print(f"    {nombre:16} {voto:.2f}  {'█' * round(voto * 24)}")
        print()
    return 0


async def cmd_world_brief(args: argparse.Namespace) -> int:
    return await cmd_predict(
        argparse.Namespace(
            query="Resumen del mundo: principales anomalías y qué es probable a continuación.",
            horizon=args.horizon,
            sector=None,
            json=args.json,
        )
    )


async def cmd_chat(args: argparse.Namespace) -> int:
    state = build_state()
    agente = next((a for a in state.swarm.agents if a.name == args.agent), None)
    if agente is None:
        disponibles = ", ".join(a.name for a in state.swarm.agents)
        print(f"No existe el agente '{args.agent}'. Disponibles: {disponibles}", file=sys.stderr)
        await state.llm.close()
        return 1

    try:
        verdict = await agente.analyze(args.query, {"events": recent_events(limit=15)})
    finally:
        await state.llm.close()

    if args.json:
        _print(verdict.model_dump())
    else:
        print(f"\n  [{agente.name}] {verdict.prediction}")
        print(f"  Confianza: {verdict.confidence:.0%}")
        if verdict.reasoning:
            print(f"  Razonamiento: {verdict.reasoning}\n")
    return 0


async def cmd_ingest(args: argparse.Namespace) -> int:
    state = build_state()
    report = await state.ingestor.run_once()
    await state.llm.close()

    if args.json:
        _print(report.to_dict())
    else:
        print(f"\n  {report.persisted} eventos nuevos de {len(report.events)} recibidos")
        print(f"  Fuentes OK ({len(report.succeeded)}): {', '.join(sorted(report.succeeded))}")
        if report.failed:
            print(f"  Con error ({len(report.failed)}):")
            for nombre, motivo in report.failed.items():
                print(f"    - {nombre}: {motivo[:100]}")
        print()
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    settings = get_settings()
    datos = {
        "database": settings.database_url.split("@")[-1],
        "model": settings.ollama.model_name,
        "horizons": settings.prediction.horizons,
        "agents": settings.mirofish.agents,
        "feeds": summary(),
        "events_by_source": event_counts(),
    }
    if args.json:
        _print(datos)
    else:
        print(f"\n  Base de datos : {datos['database']}")
        print(f"  Modelo        : {datos['model']}")
        print(f"  Agentes       : {datos['agents']}")
        print(f"  Horizontes    : {', '.join(datos['horizons'])}")
        f = datos["feeds"]
        print(f"  Fuentes       : {f['implemented']} activas de {f['total']} en catálogo")
        total = sum(datos["events_by_source"].values())
        print(f"  Eventos       : {total}")
        for fuente, n in sorted(datos["events_by_source"].items(), key=lambda kv: -kv[1]):
            print(f"      {fuente:10} {n}")
        print()
    return 0


def cmd_feeds(args: argparse.Namespace) -> int:
    if args.json:
        _print(
            {
                "implemented": [e.__dict__ for e in implemented_entries()],
                "planned": [e.__dict__ for e in planned_entries()],
            }
        )
        return 0

    print(f"\n  IMPLEMENTADAS ({len(implemented_entries())})")
    for e in implemented_entries():
        print(f"    {e.name:14} {e.domain:15} {e.description}")
    print(f"\n  PENDIENTES ({len(planned_entries())})")
    for e in planned_entries():
        marca = " [requiere clave]" if e.requires_key else ""
        print(f"    {e.name:20} {e.domain:15}{marca}")
    print()
    return 0


def cmd_scorecard(args: argparse.Namespace) -> int:
    state = build_state()
    state.predictor.load_agent_scores()

    print("\n  Brier score: 0 es perfecto, 0.25 equivale a no saber nada, 1 es el peor.\n")
    print(f"  {'Agente':16} {'Brier':>7} {'Peso':>7} {'Acierto':>8} {'N':>5}")
    for a in sorted(state.swarm.agents, key=lambda x: x.brier_score):
        print(
            f"  {a.name:16} {a.brier_score:7.3f} {a.weight:7.3f} "
            f"{a.accuracy:8.1%} {a.predictions_made:5}"
        )
    print()
    return 0


def cmd_resolve(args: argparse.Namespace) -> int:
    try:
        score = resolve_prediction(args.id, args.outcome, notes=args.notes)
    except (LookupError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(f"Predicción {args.id} resuelta. Brier score: {score:.4f}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="engine.cli", description=__doc__)
    parser.add_argument("--json", action="store_true", help="salida en JSON")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("predict", help="lanza una predicción")
    p.add_argument("--query", required=True)
    p.add_argument("--horizon", default="24h")
    p.add_argument("--sector")

    p = sub.add_parser("world-brief", help="resumen global del estado del mundo")
    p.add_argument("--horizon", default="24h")

    p = sub.add_parser("chat", help="pregunta a un solo agente")
    p.add_argument("--query", required=True)
    p.add_argument("--agent", default="Strategist")

    sub.add_parser("ingest", help="una ronda de ingesta de feeds")
    sub.add_parser("status", help="estado del sistema")
    sub.add_parser("feeds", help="catálogo de fuentes")
    sub.add_parser("scorecard", help="calibración de los agentes")

    p = sub.add_parser("resolve", help="registra el desenlace de una predicción")
    p.add_argument("--id", type=int, required=True)
    p.add_argument("--outcome", type=float, required=True, help="1.0 ocurrió, 0.0 no ocurrió")
    p.add_argument("--notes")

    return parser


ASYNC_COMMANDS = {
    "predict": cmd_predict,
    "world-brief": cmd_world_brief,
    "chat": cmd_chat,
    "ingest": cmd_ingest,
}
SYNC_COMMANDS = {
    "status": cmd_status,
    "feeds": cmd_feeds,
    "scorecard": cmd_scorecard,
    "resolve": cmd_resolve,
}


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    args = build_parser().parse_args(argv)

    # `feeds` sólo lee el catálogo del disco; no necesita base de datos.
    if args.command != "feeds":
        database.init_db()

    if args.command in ASYNC_COMMANDS:
        return asyncio.run(ASYNC_COMMANDS[args.command](args))
    return SYNC_COMMANDS[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
