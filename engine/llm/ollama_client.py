"""Cliente asíncrono de Ollama.

La especificación original describe agentes que "analizan" pero no incluía
ninguna pieza que hablase con el modelo. Este módulo es esa pieza.

`LLMClient` es un `Protocol`, así que los tests pueden inyectar un doble sin
levantar Ollama ni tocar la red.
"""

from __future__ import annotations

from types import TracebackType
from typing import Protocol, runtime_checkable

import aiohttp

from engine.config import OllamaConfig, get_settings


class LLMError(RuntimeError):
    """Fallo al obtener una respuesta utilizable del modelo."""


class LLMUnavailableError(LLMError):
    """El servidor del modelo no responde, o lo hace fuera de plazo."""


@runtime_checkable
class LLMClient(Protocol):
    """Contrato mínimo que necesita el enjambre."""

    async def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        json_mode: bool = False,
        max_tokens: int | None = None,
    ) -> str:
        """Devuelve el texto generado por el modelo."""
        ...


class OllamaClient:
    """Implementación de `LLMClient` sobre la API HTTP de Ollama."""

    def __init__(
        self,
        config: OllamaConfig | None = None,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        self.config = config or get_settings().ollama
        self._session = session
        self._owns_session = session is None

    async def __aenter__(self) -> OllamaClient:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.close()

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            # Si inference_timeout es None o 0, sin timeout (esperar indefinidamente)
            timeout = (
                aiohttp.ClientTimeout(total=None)
                if self.config.inference_timeout is None or self.config.inference_timeout == 0
                else aiohttp.ClientTimeout(total=self.config.inference_timeout)
            )
            self._session = aiohttp.ClientSession(timeout=timeout)
            self._owns_session = True
        return self._session

    async def close(self) -> None:
        if self._session is not None and self._owns_session and not self._session.closed:
            await self._session.close()
        self._session = None

    async def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        json_mode: bool = False,
        max_tokens: int | None = None,
    ) -> str:
        payload: dict[str, object] = {
            "model": self.config.model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": self.config.temperature,
                "top_p": self.config.top_p,
                "num_predict": max_tokens or self.config.max_tokens,
                "num_ctx": self.config.context_length,
            },
        }
        if system:
            payload["system"] = system
        if json_mode:
            # Ollama restringe la decodificación a JSON válido. Es la palanca que
            # hace fiable el prompt multi-persona.
            payload["format"] = "json"

        session = await self._get_session()
        url = f"{self.config.base_url.rstrip('/')}/generate"

        try:
            async with session.post(url, json=payload) as response:
                if response.status != 200:
                    body = (await response.text())[:300]
                    raise LLMError(f"Ollama respondió {response.status}: {body}")
                data = await response.json()
        except TimeoutError as exc:
            raise LLMUnavailableError(
                f"Ollama no respondió en {self.config.inference_timeout}s. "
                "Súbelo con LLM_INFERENCE_TIMEOUT o reduce LLM_MAX_TOKENS."
            ) from exc
        except aiohttp.ClientError as exc:
            raise LLMUnavailableError(
                f"No se pudo contactar con Ollama en {url}: {exc}. ¿Está `ollama serve` en marcha?"
            ) from exc

        text = data.get("response")
        if not isinstance(text, str) or not text.strip():
            raise LLMError("Ollama devolvió una respuesta vacía")
        return text

    async def is_available(self) -> bool:
        """Comprueba si el servidor responde. No lanza."""
        session = await self._get_session()
        url = f"{self.config.base_url.rstrip('/')}/tags"
        try:
            async with session.get(url) as response:
                return response.status == 200
        except (aiohttp.ClientError, TimeoutError):
            return False
