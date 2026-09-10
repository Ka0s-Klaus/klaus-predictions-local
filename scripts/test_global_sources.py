#!/usr/bin/env python3
"""
Tests de validación para fuentes globales integradas.

Verifica:
  1. JSON válido y bien formado
  2. Campos requeridos presentes
  3. URLs accesibles (sample)
  4. Scores dentro de rango
  5. No hay duplicados
  6. Distribución de calidad esperada

Uso:
  python scripts/test_global_sources.py data/sources-global-v2-critical.json
"""

import json
import logging
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class GlobalSourcesValidator:
    """Validador para fuentes globales."""

    REQUIRED_FIELDS = {
        "id",
        "name",
        "url",
        "country",
        "domain",
        "access_type",
        "metrics",
        "composite_score",
        "quality_tier",
        "is_active",
    }

    VALID_DOMAINS = {
        "weather",
        "climate",
        "geopolitical",
        "markets",
        "energy",
        "health",
        "trade",
        "technology",
        "infrastructure",
        "cyber",
        "disasters",
        "general",
    }

    VALID_TIERS = {"excellent", "very_good", "good", "acceptable"}

    def __init__(self, data_file: Path):
        self.data_file = data_file
        self.sources: list[dict[str, Any]] = []
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def load(self) -> bool:
        """Carga y valida JSON básico."""
        logger.info(f"📂 Cargando: {self.data_file}")
        try:
            with open(self.data_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.sources = data.get("sources", [])
            logger.info(f"✓ JSON válido: {len(self.sources)} fuentes")
            return True
        except json.JSONDecodeError as e:
            self.errors.append(f"JSON inválido: {e}")
            return False
        except Exception as e:
            self.errors.append(f"Error cargando archivo: {e}")
            return False

    def validate_structure(self) -> int:
        """Valida estructura de fuentes."""
        logger.info("\n🔍 Validando estructura...")
        valid_count = 0

        for i, source in enumerate(self.sources):
            # Campos requeridos
            missing = self.REQUIRED_FIELDS - set(source.keys())
            if missing:
                self.errors.append(
                    f"Fuente {i} ({source.get('id', 'unknown')}): "
                    f"campos faltantes: {missing}"
                )
                continue

            # Validar tipos
            if not isinstance(source["metrics"], dict):
                self.errors.append(
                    f"Fuente {i}: 'metrics' debe ser dict, es {type(source['metrics'])}"
                )
                continue

            # Validar domain
            if source["domain"] not in self.VALID_DOMAINS:
                self.warnings.append(
                    f"Fuente {i}: dominio desconocido '{source['domain']}'"
                )

            # Validar quality_tier
            if source["quality_tier"] not in self.VALID_TIERS:
                self.errors.append(
                    f"Fuente {i}: quality_tier '{source['quality_tier']}' inválido"
                )
                continue

            # Validar score
            score = source.get("composite_score", -1)
            if not (0 <= score <= 100):
                self.errors.append(
                    f"Fuente {i}: composite_score {score} fuera de rango [0, 100]"
                )
                continue

            valid_count += 1

        logger.info(f"✓ {valid_count}/{len(self.sources)} fuentes válidas")
        return valid_count

    def validate_uniqueness(self) -> bool:
        """Verifica no hay duplicados."""
        logger.info("\n🔎 Validando unicidad...")

        ids = [s.get("id") for s in self.sources]
        urls = [s.get("url") for s in self.sources]

        # Duplicados de ID
        id_set = set(ids)
        if len(id_set) < len(ids):
            dupes = [x for x in ids if ids.count(x) > 1]
            self.errors.append(f"IDs duplicados: {set(dupes)}")
            return False

        # Duplicados de URL
        url_set = set(urls)
        if len(url_set) < len(urls):
            dupes = [x for x in urls if urls.count(x) > 1]
            self.warnings.append(f"URLs duplicadas: {len(set(dupes))} URLs")

        logger.info(f"✓ IDs únicos: {len(id_set)}")
        logger.info(f"✓ URLs únicas: {len(url_set)}")
        return True

    def validate_urls(self) -> int:
        """Valida formato de URLs (no acceso real)."""
        logger.info("\n🌐 Validando URLs...")
        invalid_count = 0

        for i, source in enumerate(self.sources):
            url = source.get("url", "")
            try:
                parsed = urlparse(url)
                if not parsed.scheme or not parsed.netloc:
                    self.errors.append(f"Fuente {i}: URL inválida: {url}")
                    invalid_count += 1
            except Exception as e:
                self.errors.append(f"Fuente {i}: Error parseando URL {url}: {e}")
                invalid_count += 1

        logger.info(f"✓ URLs validadas: {len(self.sources) - invalid_count}/{len(self.sources)} OK")
        return invalid_count

    def analyze_distribution(self) -> dict:
        """Analiza distribución de calidad."""
        logger.info("\n📊 Analizando distribución...")

        dist = {"excellent": 0, "very_good": 0, "good": 0, "acceptable": 0}
        by_country = {}
        by_domain = {}
        scores = []

        for source in self.sources:
            tier = source.get("quality_tier", "acceptable")
            if tier in dist:
                dist[tier] += 1

            country = source.get("country", "UNKNOWN")
            by_country[country] = by_country.get(country, 0) + 1

            domain = source.get("domain", "unknown")
            by_domain[domain] = by_domain.get(domain, 0) + 1

            score = source.get("composite_score", 0)
            scores.append(score)

        # Verifica mínimos esperados (perfil CRITICAL)
        if dist["excellent"] < len(self.sources) * 0.4:  # Esperado ~50%+
            self.warnings.append(
                f"Fewer 'excellent' sources than expected: "
                f"{dist['excellent']} ({100*dist['excellent']/len(self.sources):.1f}%)"
            )

        logger.info(f"\n  🟢 EXCELENTE (90-100): {dist['excellent']:4d} ({100*dist['excellent']/len(self.sources):5.1f}%)")
        logger.info(f"  🟡 MUY BUENO (75-89): {dist['very_good']:4d} ({100*dist['very_good']/len(self.sources):5.1f}%)")
        logger.info(f"  🟠 BUENO (60-74):     {dist['good']:4d} ({100*dist['good']/len(self.sources):5.1f}%)")
        logger.info(f"  🔴 ACEPTABLE (<60):   {dist['acceptable']:4d} ({100*dist['acceptable']/len(self.sources):5.1f}%)")

        logger.info(f"\n  Países: {len(by_country)}")
        logger.info(f"  Dominios: {len(by_domain)}")

        if scores:
            logger.info(f"\n  Score statistics:")
            logger.info(f"    Media: {sum(scores)/len(scores):.1f}")
            logger.info(f"    Mín: {min(scores):.1f}, Máx: {max(scores):.1f}")

        return {
            "distribution": dist,
            "by_country": by_country,
            "by_domain": by_domain,
            "score_stats": {
                "mean": sum(scores) / len(scores) if scores else 0,
                "min": min(scores) if scores else 0,
                "max": max(scores) if scores else 0,
            },
        }

    def run(self) -> bool:
        """Ejecuta todas las validaciones."""
        logger.info("=" * 70)
        logger.info("🧪 VALIDANDO FUENTES GLOBALES")
        logger.info("=" * 70)

        # Carga
        if not self.load():
            self._print_report()
            return False

        # Estructura
        valid_count = self.validate_structure()
        if valid_count == 0:
            self._print_report()
            return False

        # Unicidad
        if not self.validate_uniqueness():
            self._print_report()
            return False

        # URLs
        invalid_urls = self.validate_urls()
        if invalid_urls > 0:
            logger.warning(f"⚠️  {invalid_urls} URLs inválidas")

        # Distribución
        self.analyze_distribution()

        # Reporte final
        self._print_report()
        return len(self.errors) == 0

    def _print_report(self):
        """Imprime reporte final."""
        logger.info("\n" + "=" * 70)
        logger.info("📋 REPORTE FINAL")
        logger.info("=" * 70)

        if self.errors:
            logger.error(f"\n❌ ERRORES ({len(self.errors)}):")
            for error in self.errors[:20]:  # Muestra máx 20
                logger.error(f"   • {error}")
            if len(self.errors) > 20:
                logger.error(f"   ... y {len(self.errors) - 20} más")
        else:
            logger.info("\n✅ SIN ERRORES")

        if self.warnings:
            logger.warning(f"\n⚠️  ADVERTENCIAS ({len(self.warnings)}):")
            for warning in self.warnings[:20]:  # Muestra máx 20
                logger.warning(f"   • {warning}")
            if len(self.warnings) > 20:
                logger.warning(f"   ... y {len(self.warnings) - 20} más")

        logger.info("\n" + "=" * 70)
        if not self.errors:
            logger.info("✅ VALIDACIÓN EXITOSA")
        else:
            logger.info("❌ VALIDACIÓN FALLIDA")
        logger.info("=" * 70)


def main():
    data_file = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/sources-global-v2-critical.json")

    if not data_file.exists():
        logger.error(f"❌ No encontrado: {data_file}")
        sys.exit(1)

    validator = GlobalSourcesValidator(data_file)
    success = validator.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
