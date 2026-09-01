"""Flujo de estado por Server-Sent Events.

La especificación titulaba este módulo `websocket.py` pero describía un
`text/event-stream`. Se mantiene el nombre del fichero y se implementa lo que
describe: SSE, que para un flujo unidireccional es más simple que WebSocket y
se reconecta solo en el navegador.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse

from engine.feeds import event_counts, recent_events
from engine.models import utcnow

if TYPE_CHECKING:  # pragma: no cover
    from engine.api.app import PythiaState

logger = logging.getLogger(__name__)


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def _snapshot(state: PythiaState) -> dict[str, Any]:
    counts = await run_in_threadpool(event_counts)
    top = await run_in_threadpool(recent_events, 5)
    return {
        "timestamp": utcnow().isoformat(),
        "uptime_seconds": state.uptime_seconds,
        "total_events": sum(counts.values()),
        "events_by_source": counts,
        "feeds_active": len(counts),
        "top_events": top,
    }


async def _generate(state: PythiaState, interval: int) -> AsyncIterator[str]:
    # Primer envío inmediato: si no, el cliente se queda con la pantalla en
    # blanco hasta que venza el primer intervalo.
    try:
        yield _sse("update", await _snapshot(state))
    except Exception:
        logger.exception("No se pudo generar el estado inicial")
        yield _sse("error", {"detail": "no se pudo leer el estado"})

    while True:
        try:
            await asyncio.sleep(interval)
            yield _sse("update", await _snapshot(state))
        except asyncio.CancelledError:
            # El cliente cerró la conexión. Es lo normal, no un error.
            logger.debug("Cliente SSE desconectado")
            raise
        except Exception:
            logger.exception("Fallo al generar un update SSE")
            yield _sse("error", {"detail": "fallo temporal"})


def state_stream(state: PythiaState, interval: int = 30) -> StreamingResponse:
    return StreamingResponse(
        _generate(state, interval),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            # Sin esto, un nginx delante bufferiza el flujo y no llega nada.
            "X-Accel-Buffering": "no",
        },
    )
