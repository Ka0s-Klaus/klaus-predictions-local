"""CORS, medida de latencia y traducción de errores."""

from __future__ import annotations

import logging
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from engine.config import get_settings
from engine.feeds.sources import FeedError
from engine.llm.ollama_client import LLMError, LLMUnavailableError
from engine.mirofish.swarm import SwarmError

logger = logging.getLogger(__name__)

LATENCY_HEADER = "X-Process-Time-Ms"


def install(app: FastAPI) -> None:
    """Registra middlewares y manejadores de excepción."""
    settings = get_settings().api

    app.add_middleware(
        CORSMiddleware,
        # Lista explícita en lugar de "*": con `allow_credentials` activo los
        # navegadores rechazan el comodín, y "*" tampoco tiene sentido para un
        # servicio que se supone local.
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def add_latency_header(request: Request, call_next):  # type: ignore[no-untyped-def]
        started = time.perf_counter()
        response = await call_next(request)
        response.headers[LATENCY_HEADER] = f"{(time.perf_counter() - started) * 1000:.0f}"
        return response

    @app.exception_handler(LLMUnavailableError)
    async def llm_unavailable(_: Request, exc: LLMUnavailableError) -> JSONResponse:
        # 503 y no 500: el fallo es de una dependencia externa y el cliente
        # puede reintentar.
        return JSONResponse(
            status_code=503,
            content={"error": "modelo_no_disponible", "detail": str(exc)},
        )

    @app.exception_handler(SwarmError)
    async def swarm_failed(_: Request, exc: SwarmError) -> JSONResponse:
        return JSONResponse(
            status_code=502,
            content={"error": "consenso_fallido", "detail": str(exc)},
        )

    @app.exception_handler(LLMError)
    async def llm_error(_: Request, exc: LLMError) -> JSONResponse:
        return JSONResponse(
            status_code=502,
            content={"error": "error_del_modelo", "detail": str(exc)},
        )

    @app.exception_handler(FeedError)
    async def feed_error(_: Request, exc: FeedError) -> JSONResponse:
        return JSONResponse(
            status_code=502,
            content={"error": "error_de_fuente", "detail": str(exc)},
        )

    @app.exception_handler(ValueError)
    async def bad_value(_: Request, exc: ValueError) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content={"error": "peticion_invalida", "detail": str(exc)},
        )
