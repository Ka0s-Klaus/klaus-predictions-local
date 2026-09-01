"""Carga de configuración y capa de embeddings."""

from __future__ import annotations

import pytest

from engine.config import Settings, get_settings
from engine.embedding import GPUEmbeddingEngine, resolve_device
from engine.embedding.gpu_engine import EmbeddingUnavailableError


class TestSettings:
    def test_valores_por_defecto_arrancan_sin_env(self) -> None:
        settings = Settings()

        assert settings.database_url.startswith("sqlite")
        assert settings.api.port == 8088
        assert settings.mirofish.agents == 7

    def test_el_env_plano_alimenta_la_config_agrupada(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`LLM_MODEL` en el .env tiene que acabar en `settings.ollama.model_name`."""
        monkeypatch.setenv("LLM_MODEL", "qwen3:1.7b")
        monkeypatch.setenv("FEEDS_CONCURRENCY", "2")
        monkeypatch.setenv("CONSENSUS_THRESHOLD", "0.8")
        get_settings.cache_clear()

        settings = Settings()

        assert settings.ollama.model_name == "qwen3:1.7b"
        assert settings.feeds.concurrency == 2
        assert settings.mirofish.consensus_threshold == 0.8

    def test_horizontes_se_leen_como_lista_separada_por_comas(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Un `list[str]` en pydantic-settings esperaría JSON; esto no lo es."""
        monkeypatch.setenv("PREDICTION_HORIZONS", "24h, week ,month")
        get_settings.cache_clear()

        assert Settings().prediction.horizons == ["24h", "week", "month"]

    def test_cors_origins_igual(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CORS_ORIGINS", "http://a.test,http://b.test")
        get_settings.cache_clear()

        assert Settings().api.cors_origins == ["http://a.test", "http://b.test"]

    @pytest.mark.parametrize(
        ("var", "valor"),
        [
            ("LLM_TEMPERATURE", "3.0"),
            ("API_PORT", "70000"),
            ("FORECAST_CONFIDENCE_MIN", "1.5"),
            ("GPU_MEMORY_FRACTION", "0"),
        ],
    )
    def test_rechaza_valores_imposibles(
        self, monkeypatch: pytest.MonkeyPatch, var: str, valor: str
    ) -> None:
        monkeypatch.setenv(var, valor)
        get_settings.cache_clear()

        with pytest.raises(ValueError):
            Settings()

    def test_database_url_vacia_es_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DATABASE_URL", "   ")
        get_settings.cache_clear()

        with pytest.raises(ValueError, match="DATABASE_URL"):
            Settings()

    def test_get_settings_cachea(self) -> None:
        assert get_settings() is get_settings()


class TestEmbeddingDevice:
    def test_resolve_device_nunca_lanza(self) -> None:
        """La especificación pedía `device="cuda"` en una Intel HD: eso revienta."""
        resolve_device.cache_clear()

        assert resolve_device("auto") in {"cpu", "xpu", "cuda"}

    def test_preferencia_explicita_se_respeta(self) -> None:
        resolve_device.cache_clear()

        assert resolve_device("cpu") == "cpu"

    def test_sin_gpu_no_se_consulta_el_hardware(self) -> None:
        engine = GPUEmbeddingEngine(use_gpu=False, device="auto")

        assert engine.device == "cpu"
        assert engine.is_loaded is False

    def test_el_modelo_no_se_carga_al_construir(self) -> None:
        """Importar sentence-transformers cuesta segundos y cientos de MB."""
        engine = GPUEmbeddingEngine()

        assert engine.is_loaded is False

    def test_mensaje_util_si_falta_el_extra(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import builtins

        real_import = builtins.__import__

        def sin_sentence_transformers(name: str, *args: object, **kwargs: object) -> object:
            if name == "sentence_transformers":
                raise ImportError("no module")
            return real_import(name, *args, **kwargs)  # type: ignore[arg-type]

        monkeypatch.setattr(builtins, "__import__", sin_sentence_transformers)

        with pytest.raises(EmbeddingUnavailableError, match=r"\[embeddings\]"):
            _ = GPUEmbeddingEngine().model
