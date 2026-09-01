"""Motor SQLAlchemy, sesiones y creación del esquema.

Se usa la API **síncrona** de SQLAlchemy a propósito: es la que menos piezas
móviles tiene y funciona igual con SQLite y con PostgreSQL. Las rutas asíncronas
que necesiten tocar la base de datos deben delegar en un hilo
(`fastapi.concurrency.run_in_threadpool`) para no bloquear el bucle de eventos.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from engine.config import get_settings
from engine.models import Base

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def _build_engine(database_url: str) -> Engine:
    kwargs: dict[str, object] = {"future": True, "pool_pre_ping": True}

    if database_url.startswith("sqlite"):
        # SQLite abre la conexión atada al hilo que la creó; FastAPI sirve las
        # rutas síncronas desde un pool de hilos, así que hay que relajarlo.
        kwargs["connect_args"] = {"check_same_thread": False}
        # `pool_pre_ping` no aporta nada sobre un fichero local.
        kwargs.pop("pool_pre_ping")
    else:
        kwargs["pool_size"] = 5
        kwargs["max_overflow"] = 5

    return create_engine(database_url, **kwargs)  # type: ignore[arg-type]


def get_engine() -> Engine:
    """Motor único del proceso, creado en la primera llamada."""
    global _engine
    if _engine is None:
        _engine = _build_engine(get_settings().database_url)
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(bind=get_engine(), expire_on_commit=False)
    return _session_factory


@contextmanager
def session_scope() -> Iterator[Session]:
    """Sesión transaccional: confirma al salir, revierte si algo falla."""
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_session() -> Iterator[Session]:
    """Dependencia para FastAPI (`Depends(get_session)`)."""
    with session_scope() as session:
        yield session


def init_db(engine: Engine | None = None) -> None:
    """Crea las tablas que falten. Idempotente."""
    Base.metadata.create_all(bind=engine or get_engine())


def configure(database_url: str) -> Engine:
    """Reapunta el motor a otra URL. Pensado para tests y para `scripts/`."""
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = _build_engine(database_url)
    _session_factory = None
    return _engine
