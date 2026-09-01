"""Configuración compartida de la suite."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from engine import database
from engine.config import get_settings
from engine.embedding import reset_cache
from engine.llm.ollama_client import LLMClient
from engine.mirofish import MiroFishSwarm, build_agents
from tests.fixtures import FakeLLM


@pytest.fixture(autouse=True)
def isolated_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[None]:
    """Aísla cada test de cualquier `.env` presente en el disco."""
    for name in (
        "DATABASE_URL",
        "LLM_MODEL",
        "LLM_BASE_URL",
        "USE_GPU",
        "SECRET_KEY",
        "MIROFISH_AGENTS",
        "PREDICTION_HORIZONS",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.chdir(tmp_path)
    get_settings.cache_clear()
    reset_cache()
    yield
    get_settings.cache_clear()
    reset_cache()


@pytest.fixture
def db(tmp_path: Path) -> Iterator[None]:
    """Base de datos SQLite temporal, con el esquema ya creado."""
    engine = database.configure(f"sqlite:///{tmp_path / 'test.db'}")
    database.init_db(engine)
    yield
    engine.dispose()


@pytest.fixture
def fake_llm() -> FakeLLM:
    from tests.fixtures import swarm_payload

    return FakeLLM(swarm_payload())


@pytest.fixture
def swarm(fake_llm: LLMClient) -> MiroFishSwarm:
    return MiroFishSwarm(build_agents(fake_llm), fake_llm)
