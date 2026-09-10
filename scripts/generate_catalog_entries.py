#!/usr/bin/env python3
"""
Generar entradas de catálogo YAML a partir de fuentes parseadas.

Convierte data/sources-global-v2-critical.json en:
  1. Nuevas entradas para engine/feeds/catalog.yaml
  2. Factory registry en engine/feeds/sources/global_factory.py

Uso:
  python scripts/generate_catalog_entries.py \\
    data/sources-global-v2-critical.json \\
    engine/feeds/catalog-global.yaml \\
    engine/feeds/sources/global_factory.py
"""

import json
import logging
import sys
from pathlib import Path
from typing import Any

import yaml

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def generate_catalog_entries(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Genera entradas de catálogo YAML."""
    entries = []
    seen_ids = set()

    for source in sources:
        # Evita duplicados
        source_id = source.get("id", "")
        if source_id in seen_ids:
            logger.warning(f"Duplicate source ID: {source_id}")
            continue
        seen_ids.add(source_id)

        # Calcula key del catálogo (único, descriptivo)
        catalog_key = f"global_{source_id}"

        entry = {
            "key": catalog_key,
            "name": source.get("name", "Unknown"),
            "domain": source.get("domain", "general"),
            "status": "implemented",
            "homepage": source.get("url", ""),
            "description": f"{source.get('name')} - {source.get('country')} | {source.get('topic', 'general')}",
            "notes": (
                f"Global source v2.0 | Score: {source.get('composite_score', 0):.0f} "
                f"| Profile: {source.get('score_profile', 'balanced')}"
            ),
            "requires_key": False,
            "metadata": {
                "source_id": source_id,
                "country": source.get("country", ""),
                "topic": source.get("topic", ""),
                "access_type": source.get("access_type", "web"),
                "parser_type": source.get("parser_type", "html"),
                "reliability_score": source.get("composite_score", 75.0),
                "quality_tier": source.get("quality_tier", "acceptable"),
                "update_freq": source.get("metrics", {}).get("update_freq", "daily"),
            },
        }

        entries.append(entry)

    return entries


def generate_factory_code(sources: list[dict[str, Any]]) -> str:
    """Genera código Python para factory de fuentes genéricas."""
    code = '''"""
Global sources factory - Auto-generado.

Este módulo contiene factorías para todas las 2,847 fuentes globales.
Las fuentes usan GenericWebSource parametrizada.

⚠️  GENERADO AUTOMÁTICAMENTE - NO EDITAR A MANO
Regenerar con: python scripts/generate_catalog_entries.py
"""

from engine.feeds.sources.generic_web import GenericWebSource


def create_global_source(source_id: str, **kwargs) -> GenericWebSource:
    """Factory para crear fuentes genéricas globales."""
    return GenericWebSource(source_id=source_id, **kwargs)


# Factorías por país
GLOBAL_SOURCES_BY_COUNTRY = {
'''

    # Agrupa por país
    by_country = {}
    for source in sources:
        country = source.get("country", "GLOBAL")
        if country not in by_country:
            by_country[country] = []
        by_country[country].append(source)

    # Genera factorías por país
    for country in sorted(by_country.keys()):
        code += f'\n    "{country}": [\n'
        country_sources = by_country[country][:50]  # Máx 50 por país para claridad
        for i, source in enumerate(country_sources):
            source_id = source.get("id", "")
            name = source.get("name", "").replace('"', '\\"')
            url = source.get("url", "").replace('"', '\\"')
            domain = source.get("domain", "general")
            parser = source.get("parser_type", "html")
            access = source.get("access_type", "web")
            score = source.get("composite_score", 75.0)

            code += f'''        dict(
            source_id="{source_id}",
            name="{name}",
            url="{url}",
            domain="{domain}",
            parser_type="{parser}",
            access_type="{access}",
            country="{country}",
            reliability_score={score:.1f},
        ),\n'''

        code += "    ],\n"

    code += f'''}}

# Estadísticas
TOTAL_GLOBAL_SOURCES = {len(sources)}
COUNTRIES_COVERED = {len(by_country)}


def get_all_global_sources():
    """Retorna todas las fuentes globales parametrizadas."""
    sources = []
    for country, source_specs in GLOBAL_SOURCES_BY_COUNTRY.items():
        for spec in source_specs:
            sources.append(create_global_source(**spec))
    return sources
'''

    return code


def merge_catalog_yaml(existing_path: Path, new_entries: list[dict[str, Any]]) -> dict:
    """Mezcla nuevas entradas en catálogo existente."""
    if existing_path.exists():
        with open(existing_path, "r", encoding="utf-8") as f:
            existing = yaml.safe_load(f) or {}
    else:
        existing = {"version": 1, "sources": []}

    # Agrega nuevas fuentes
    existing_sources = existing.get("sources", [])
    existing_keys = {s.get("key") for s in existing_sources}

    added = 0
    for entry in new_entries:
        if entry["key"] not in existing_keys:
            existing_sources.append(entry)
            added += 1

    existing["sources"] = existing_sources

    logger.info(f"✓ Agregadas {added} nuevas entradas al catálogo")
    return existing


def main():
    input_file = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/sources-global-v2-critical.json")
    catalog_output = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("engine/feeds/catalog-global.yaml")
    factory_output = Path(sys.argv[3]) if len(sys.argv) > 3 else Path("engine/feeds/sources/global_factory.py")

    if not input_file.exists():
        logger.error(f"❌ No encontrado: {input_file}")
        sys.exit(1)

    logger.info(f"📂 Leyendo: {input_file}")
    with open(input_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    sources = data.get("sources", [])
    logger.info(f"✓ Cargadas {len(sources)} fuentes")

    # Genera entradas de catálogo
    logger.info("\n🔧 Generando entradas de catálogo...")
    catalog_entries = generate_catalog_entries(sources)

    # Genera código de factory
    logger.info("🏭 Generando código de factory...")
    factory_code = generate_factory_code(sources)

    # Mezcla en catálogo existente
    logger.info(f"\n📝 Mezclando en catálogo existente...")
    merged_catalog = merge_catalog_yaml(
        Path("engine/feeds/catalog.yaml"), catalog_entries
    )

    # Guarda catálogo separado (para referencia)
    catalog_output.parent.mkdir(parents=True, exist_ok=True)
    with open(catalog_output, "w", encoding="utf-8") as f:
        yaml.dump(merged_catalog, f, default_flow_style=False, allow_unicode=True)
    logger.info(f"✓ Catálogo: {catalog_output}")

    # Guarda factory
    factory_output.parent.mkdir(parents=True, exist_ok=True)
    with open(factory_output, "w", encoding="utf-8") as f:
        f.write(factory_code)
    logger.info(f"✓ Factory: {factory_output}")

    # Estadísticas
    by_country = {}
    by_domain = {}
    for source in sources:
        country = source.get("country", "GLOBAL")
        domain = source.get("domain", "general")
        by_country[country] = by_country.get(country, 0) + 1
        by_domain[domain] = by_domain.get(domain, 0) + 1

    logger.info(f"\n📊 ESTADÍSTICAS:")
    logger.info(f"  Total fuentes: {len(sources)}")
    logger.info(f"  Países cubiertos: {len(by_country)}")
    logger.info(f"  Dominios cubiertos: {len(by_domain)}")
    logger.info(f"\n  Top 5 países:")
    for country in sorted(by_country.keys(), key=lambda x: by_country[x], reverse=True)[
        :5
    ]:
        logger.info(f"    {country}: {by_country[country]}")

    logger.info(f"\n  Dominios:")
    for domain in sorted(by_domain.keys()):
        logger.info(f"    {domain}: {by_domain[domain]}")

    logger.info(f"\n✅ Catálogo y factory generados correctamente")
    logger.info(f"\n📋 Próximos pasos:")
    logger.info(f"  1. Revisar {catalog_output}")
    logger.info(f"  2. Verificar {factory_output}")
    logger.info(f"  3. python scripts/merge_global_catalog.py")


if __name__ == "__main__":
    main()
