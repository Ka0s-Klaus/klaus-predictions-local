"""Autenticación opcional por token.

Pythia es local-first: por defecto escucha sin credenciales, porque el caso de
uso normal es `localhost`. En cuanto se define `API_TOKEN`, todos los endpoints
salvo `/health` exigen `Authorization: Bearer <token>`.

Configúralo siempre que expongas el puerto fuera de la máquina: `API_HOST` vale
`0.0.0.0` por defecto y eso incluye la red local.
"""

from __future__ import annotations

import hmac
import logging

from fastapi import Header, HTTPException, status

from engine.config import get_settings

logger = logging.getLogger(__name__)


def token_required() -> bool:
    return bool(get_settings().api_token)


async def verify_token(authorization: str | None = Header(default=None)) -> None:
    """Dependencia de FastAPI. No hace nada si no hay token configurado."""
    expected = get_settings().api_token
    if not expected:
        return

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Falta la cabecera Authorization: Bearer <token>",
            headers={"WWW-Authenticate": "Bearer"},
        )

    provided = authorization.removeprefix("Bearer ").strip()
    # Comparación en tiempo constante: comparar con == filtra información sobre
    # el token a través del tiempo de respuesta.
    if not hmac.compare_digest(provided, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido",
            headers={"WWW-Authenticate": "Bearer"},
        )
