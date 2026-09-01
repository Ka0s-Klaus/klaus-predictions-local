"""Registro de fuentes.

`catalog.yaml` declara todas las fuentes que el proyecto reconoce;
`sources.IMPLEMENTATIONS` dice cuáles tienen código. El registro cruza ambas y
sólo instancia las que existen de verdad, de modo que el catálogo puede crecer
sin fingir que 48 fuentes funcionan.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from engine.feeds.sources import IMPLEMENTATIONS, FeedSource

logger = logging.getLogger(__name__)

CATALOG_PATH = Path(__file__).parent / "catalog.yaml"

IMPLEMENTED = "implemented"
PLANNED = "planned"
VALID_STATUS = frozenset({IMPLEMENTED, PLANNED})


class CatalogError(RuntimeError):
    """El catálogo no es coherente con el código."""


@dataclass(frozen=True, slots=True)
class CatalogEntry:
    """Una fuente declarada en el catálogo."""

    key: str
    name: str
    domain: str
    status: str
    homepage: str = ""
    description: str = ""
    notes: str = ""
    requires_key: bool = False

    @property
    def is_implemented(self) -> bool:
        return self.status == IMPLEMENTED


def _parse(raw: dict[str, Any]) -> list[CatalogEntry]:
    entries = []
    seen: set[str] = set()

    for item in raw.get("sources") or []:
        key = item.get("key")
        if not key:
            raise CatalogError(f"entrada del catálogo sin `key`: {item}")
        if key in seen:
            raise CatalogError(f"clave duplicada en el catálogo: {key}")
        seen.add(key)

        status = item.get("status", PLANNED)
        if status not in VALID_STATUS:
            raise CatalogError(
                f"{key}: status '{status}' no válido; usa {' o '.join(sorted(VALID_STATUS))}"
            )

        entries.append(
            CatalogEntry(
                key=key,
                name=item.get("name") or key,
                domain=item.get("domain") or "unknown",
                status=status,
                homepage=item.get("homepage") or "",
                description=item.get("description") or "",
                notes=(item.get("notes") or "").strip(),
                requires_key=bool(item.get("requires_key")),
            )
        )
    return entries


@lru_cache(maxsize=1)
def load_catalog(path: str | None = None) -> tuple[CatalogEntry, ...]:
    """Lee y valida el catálogo. El resultado se cachea."""
    target = Path(path) if path else CATALOG_PATH
    if not target.exists():
        raise CatalogError(f"no se encuentra el catálogo en {target}")

    raw = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
    entries = _parse(raw)

    # Una entrada marcada como implementada sin clase detrás sería una promesa
    # incumplida que solo se descubriría al arrancar la ingesta.
    faltantes = [e.key for e in entries if e.is_implemented and e.key not in IMPLEMENTATIONS]
    if faltantes:
        raise CatalogError(
            f"declaradas como implementadas pero sin clase en sources/: {', '.join(faltantes)}"
        )

    huerfanas = {k for k in IMPLEMENTATIONS if k not in {e.key for e in entries}}
    if huerfanas:
        raise CatalogError(
            f"clases registradas que no aparecen en el catálogo: {', '.join(sorted(huerfanas))}"
        )

    return tuple(entries)


def implemented_entries() -> list[CatalogEntry]:
    return [entry for entry in load_catalog() if entry.is_implemented]


def planned_entries() -> list[CatalogEntry]:
    return [entry for entry in load_catalog() if not entry.is_implemented]


def build_sources(
    keys: list[str] | None = None,
    *,
    max_bytes: int = 20 * 1024 * 1024,
) -> list[FeedSource]:
    """Instancia las fuentes implementadas.

    `keys` permite quedarse con un subconjunto; se ignoran en silencio las que
    aún no tienen implementación.
    """
    selected = implemented_entries()
    if keys is not None:
        wanted = set(keys)
        desconocidas = wanted - {e.key for e in load_catalog()}
        if desconocidas:
            raise CatalogError(f"fuentes desconocidas: {', '.join(sorted(desconocidas))}")
        selected = [entry for entry in selected if entry.key in wanted]

    return [IMPLEMENTATIONS[entry.key](max_bytes=max_bytes) for entry in selected]


def summary() -> dict[str, Any]:
    """Recuento por estado y por dominio. Lo consume `/health` y la documentación."""
    entries = load_catalog()
    by_domain: dict[str, int] = {}
    for entry in entries:
        by_domain[entry.domain] = by_domain.get(entry.domain, 0) + 1

    return {
        "total": len(entries),
        "implemented": sum(1 for e in entries if e.is_implemented),
        "planned": sum(1 for e in entries if not e.is_implemented),
        "requires_key": sum(1 for e in entries if e.requires_key),
        "by_domain": dict(sorted(by_domain.items())),
    }
