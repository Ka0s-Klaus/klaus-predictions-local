#!/usr/bin/env python3
"""
Fusionar catálogo global con catálogo Klaus existente.

Combina engine/feeds/catalog.yaml (fuentes Klaus existentes)
con engine/feeds/catalog-global.yaml (2,847 fuentes globales).

Evita duplicados y actualiza registry.py para que reconozca
las nuevas fuentes genéricas.

Uso:
  python scripts/merge_global_catalog.py
"""

import logging
import sys
from pathlib import Path
from typing import Any

import yaml

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def load_yaml(path: Path) -> dict[str, Any]:
    """Carga archivo YAML."""
    if not path.exists():
        logger.warning(f"⚠️  No encontrado: {path}, usando empty")
        return {"version": 1, "sources": []}

    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {"version": 1, "sources": []}


def merge_catalogs(
    existing: dict[str, Any], global_: dict[str, Any]
) -> dict[str, Any]:
    """Mezcla catálogos, evitando duplicados por URL."""
    merged = existing.copy()
    merged_sources = merged.get("sources", [])

    # Índice de URLs existentes
    existing_urls = {s.get("homepage") for s in merged_sources if s.get("homepage")}

    # Agrega fuentes globales no duplicadas
    added = 0
    skipped = 0

    for source in global_.get("sources", []):
        url = source.get("homepage")

        if url in existing_urls:
            skipped += 1
            continue

        merged_sources.append(source)
        existing_urls.add(url)
        added += 1

    merged["sources"] = merged_sources

    logger.info(f"✓ Agregadas {added} nuevas fuentes")
    logger.info(f"⏭️  Saltadas {skipped} duplicadas")

    return merged


def generate_registry_update(catalog: dict[str, Any]) -> str:
    """Genera fragmento de código para actualizar registry.py."""
    # Enumera todas las claves generadas
    global_keys = [s.get("key") for s in catalog.get("sources", []) if s.get("key", "").startswith("global_")]

    code = """
# ============================================================================
# GLOBAL SOURCES REGISTRY (Auto-generado)
# ============================================================================
# Agregadas en lugar del registro manual anterior
#
# Nota: GenericWebSource maneja parametrización por source_id.
# No hace falta una clase específica por fuente.

def _build_global_source(entry: CatalogEntry) -> GenericWebSource:
    \"\"\"Factory para crear GenericWebSource desde entrada de catálogo.\"\"\"
    metadata = entry.get("metadata") or {}
    return GenericWebSource(
        source_id=metadata.get("source_id", entry.key),
        name=entry.name,
        url=entry.homepage,
        parser_type=metadata.get("parser_type", "html"),
        access_type=metadata.get("access_type", "web"),
        country=metadata.get("country", "GLOBAL"),
        domain=entry.domain,
        reliability_score=metadata.get("reliability_score", 75.0),
    )

# Entradas de catálogo que usan GenericWebSource
GLOBAL_SOURCE_KEYS = {
"""

    for key in sorted(global_keys):
        code += f'    "{key}",\n'

    code += """
}
"""

    return code


def main():
    catalog_path = Path("engine/feeds/catalog.yaml")
    global_catalog_path = Path("engine/feeds/catalog-global.yaml")
    output_path = Path("engine/feeds/catalog.yaml")

    logger.info(f"📂 Leyendo catálogos...")
    logger.info(f"  Existente: {catalog_path}")
    logger.info(f"  Global: {global_catalog_path}")

    existing = load_yaml(catalog_path)
    global_ = load_yaml(global_catalog_path)

    logger.info(f"✓ Catálogo existente: {len(existing.get('sources', []))} fuentes")
    logger.info(f"✓ Catálogo global: {len(global_.get('sources', []))} fuentes")

    # Mezcla
    logger.info(f"\n🔀 Fusionando catálogos...")
    merged = merge_catalogs(existing, global_)

    # Estadísticas
    by_domain = {}
    for source in merged.get("sources", []):
        domain = source.get("domain", "unknown")
        by_domain[domain] = by_domain.get(domain, 0) + 1

    logger.info(f"\n📊 RESULTADO FUSIONADO:")
    logger.info(f"  Total fuentes: {len(merged.get('sources', []))}")
    logger.info(f"  Dominios:")
    for domain in sorted(by_domain.keys()):
        logger.info(f"    {domain}: {by_domain[domain]}")

    # Guarda resultado
    logger.info(f"\n💾 Guardando: {output_path}")
    with open(output_path, "w", encoding="utf-8") as f:
        yaml.dump(merged, f, default_flow_style=False, allow_unicode=True)

    logger.info(f"✓ Catálogo fusionado guardado")

    # Genera snippet de registry
    logger.info(f"\n📝 Generando snippet de registry...")
    registry_snippet = generate_registry_update(merged)

    snippet_path = Path("engine/feeds/sources/global_registry_snippet.py")
    with open(snippet_path, "w", encoding="utf-8") as f:
        f.write(registry_snippet)

    logger.info(f"✓ Snippet guardado en: {snippet_path}")
    logger.info(f"\n⚠️  SIGUIENTE PASO MANUAL:")
    logger.info(f"  Copiar contenido de {snippet_path} a engine/feeds/registry.py")
    logger.info(f"  Reemplazar en registry.py línea de build_sources() para incluir GenericWebSource")


if __name__ == "__main__":
    main()
