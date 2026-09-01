"""Acceso al modelo de lenguaje local."""

from engine.llm.ollama_client import LLMClient, LLMError, LLMUnavailableError, OllamaClient

__all__ = ["LLMClient", "LLMError", "LLMUnavailableError", "OllamaClient"]
