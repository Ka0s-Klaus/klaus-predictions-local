"""Carga y validación de configuración.

El `.env` del proyecto es **plano** (`LLM_MODEL`, `USE_GPU`, `FEEDS_CONCURRENCY`…)
mientras que la configuración se expone agrupada (`settings.ollama.model_name`).
Para que ambas cosas convivan, cada grupo es a su vez un `BaseSettings`: al
instanciarse lee sus propias variables del entorno mediante alias, y el objeto
`Settings` sólo los compone.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV = SettingsConfigDict(
    env_file=".env",
    env_file_encoding="utf-8",
    extra="ignore",
    case_sensitive=False,
    populate_by_name=True,
)


def _split_csv(value: str | list[str]) -> list[str]:
    """Convierte `"a,b , c"` en `["a", "b", "c"]`, tolerando ya-listas."""
    if isinstance(value, list):
        return value
    return [item.strip() for item in value.split(",") if item.strip()]


class OllamaConfig(BaseSettings):
    """Parámetros del LLM local servido por Ollama."""

    model_config = _ENV

    # `model_` es un espacio de nombres protegido en Pydantic, de ahí `model_name`.
    model_name: str = Field("mistral:7b-instruct-q4_K_M", alias="LLM_MODEL")
    base_url: str = Field("http://localhost:11434/api", alias="LLM_BASE_URL")
    temperature: float = Field(0.7, alias="LLM_TEMPERATURE", ge=0.0, le=2.0)
    top_p: float = Field(0.95, alias="LLM_TOP_P", ge=0.0, le=1.0)
    max_tokens: int = Field(384, alias="LLM_MAX_TOKENS", gt=0)
    context_length: int = Field(4096, alias="LLM_CONTEXT_LENGTH", gt=0)
    inference_timeout: int | None = Field(20, alias="LLM_INFERENCE_TIMEOUT")


class GPUConfig(BaseSettings):
    """Aceleración por GPU para la capa de embeddings.

    Ojo: en gráficos integrados (Intel HD 520/530) la "VRAM" es RAM del sistema
    compartida. Activar la GPU descarga la CPU, pero **no libera memoria**.
    """

    model_config = _ENV

    use_gpu: bool = Field(False, alias="USE_GPU")
    device: str = Field("auto", alias="EMBEDDING_DEVICE")
    memory_fraction: float = Field(0.8, alias="GPU_MEMORY_FRACTION", gt=0.0, le=1.0)
    embedding_model: str = Field("all-MiniLM-L6-v2", alias="EMBEDDING_MODEL")


class FeedsConfig(BaseSettings):
    """Ingesta de fuentes públicas."""

    model_config = _ENV

    enabled: bool = Field(True, alias="FEEDS_ENABLED")
    update_interval: int = Field(900, alias="FEEDS_UPDATE_INTERVAL", gt=0)
    timeout: int = Field(20, alias="FEEDS_TIMEOUT", gt=0)
    concurrency: int = Field(4, alias="FEEDS_CONCURRENCY", gt=0)
    cache_days: int = Field(30, alias="FEEDS_CACHE_DAYS", ge=0)
    max_feed_size_mb: int = Field(20, alias="MAX_FEED_SIZE_MB", gt=0)


class PredictionConfig(BaseSettings):
    """Horizontes y umbrales de predicción."""

    model_config = _ENV

    # Se declara como `str` a propósito: pydantic-settings intentaría deserializar
    # un `list[str]` como JSON y `24h,week,month,year` no lo es.
    horizons_raw: str = Field("24h,week,month,year", alias="PREDICTION_HORIZONS")
    per_horizon: int = Field(3, alias="PREDICTIONS_PER_HORIZON", gt=0)
    confidence_min: float = Field(0.55, alias="FORECAST_CONFIDENCE_MIN", ge=0.0, le=1.0)

    @property
    def horizons(self) -> list[str]:
        return _split_csv(self.horizons_raw)


class MiroFishConfig(BaseSettings):
    """Enjambre de agentes y reglas de consenso."""

    model_config = _ENV

    agents: int = Field(7, alias="MIROFISH_AGENTS", gt=0)
    consensus_threshold: float = Field(0.65, alias="CONSENSUS_THRESHOLD", ge=0.0, le=1.0)
    brier_weighted_voting: bool = Field(True, alias="BRIER_WEIGHTED_VOTING")
    verbose_reasoning: bool = Field(True, alias="VERBOSE_REASONING")


class APIConfig(BaseSettings):
    """Servidor HTTP."""

    model_config = _ENV

    host: str = Field("0.0.0.0", alias="API_HOST")  # noqa: S104 - se expone en LAN a propósito
    port: int = Field(8088, alias="API_PORT", gt=0, lt=65536)
    # 1 worker es lo correcto en un quad-core con 16 GB: cada worker duplica el
    # residente del proceso y aquí no hay margen.
    workers: int = Field(1, alias="API_WORKERS", gt=0)
    timeout: int = Field(15, alias="API_TIMEOUT", gt=0)
    cors_origins_raw: str = Field(
        "http://localhost:3000,http://127.0.0.1:8088", alias="CORS_ORIGINS"
    )

    @property
    def cors_origins(self) -> list[str]:
        return _split_csv(self.cors_origins_raw)


class Settings(BaseSettings):
    """Configuración raíz. Usa `get_settings()` en lugar de instanciarla."""

    model_config = _ENV

    ollama: OllamaConfig = Field(default_factory=OllamaConfig)
    gpu: GPUConfig = Field(default_factory=GPUConfig)
    feeds: FeedsConfig = Field(default_factory=FeedsConfig)
    prediction: PredictionConfig = Field(default_factory=PredictionConfig)
    mirofish: MiroFishConfig = Field(default_factory=MiroFishConfig)
    api: APIConfig = Field(default_factory=APIConfig)

    # SQLite por defecto para que el proyecto arranque y los tests corran sin
    # levantar un PostgreSQL. En producción se apunta a postgresql://…
    database_url: str = Field("sqlite:///./pythia.db", alias="DATABASE_URL")
    secret_key: str = Field("dev-only-change-me", alias="SECRET_KEY")
    # Vacío = API abierta, que es lo razonable en localhost. Al definirlo, todo
    # salvo /health exige `Authorization: Bearer <token>`.
    api_token: str = Field("", alias="API_TOKEN")
    audit_enabled: bool = Field(True, alias="AUDIT_ENABLED")
    audit_sample_rate: float = Field(0.7, alias="AUDIT_SAMPLE_RATE", ge=0.0, le=1.0)
    debug: bool = Field(False, alias="DEBUG")

    @field_validator("database_url")
    @classmethod
    def _reject_empty_url(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("DATABASE_URL no puede estar vacío")
        return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Configuración cacheada durante todo el proceso.

    Los tests que necesiten otra configuración deben llamar a
    `get_settings.cache_clear()` tras modificar el entorno.
    """
    return Settings()
