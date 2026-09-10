#!/usr/bin/env python3
"""
Aplicar perfil CRITICAL: reweighting de fuentes para predicción de alertas.

Perfil CRITICAL prioriza:
  - Fiabilidad (35%): Fuentes que NO fallan
  - Actualización (30%): Real-time > Diario > Semanal
  - Cobertura (15%): Global > Regional
  - Integridad (12%): Datos completos
  - Accesibilidad (8%): Funciona siempre

Uso:
  python scripts/apply_critical_profile.py \\
    data/sources-global-v2.json \\
    data/sources-global-v2-critical.json
"""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class ReliabilityProfiler:
    """Calcula scores compuestos con diferentes perfiles de pesos."""

    PROFILES = {
        "critical": {
            "name": "🔴 CRITICAL: Predicción de Alertas",
            "description": "Fuentes rápidas + confiables. Para Klaus prediciendo conflictos/desastres/mercados.",
            "weights": {
                "reliability": 0.35,
                "update_freq": 0.30,
                "coverage": 0.15,
                "completeness": 0.12,
                "accessibility": 0.08,
            },
            "min_acceptable_score": 75.0,
        },
        "context": {
            "name": "🟡 CONTEXT: Análisis Investigativo",
            "description": "Profundidad + cobertura. Para análisis geopolítico/tendencias.",
            "weights": {
                "reliability": 0.25,
                "update_freq": 0.15,
                "coverage": 0.30,
                "completeness": 0.20,
                "accessibility": 0.10,
            },
            "min_acceptable_score": 60.0,
        },
        "coverage": {
            "name": "🟢 COVERAGE: Monitoreo Global",
            "description": "Máxima cobertura. Para 195 países sin gaps.",
            "weights": {
                "reliability": 0.20,
                "update_freq": 0.15,
                "coverage": 0.35,
                "completeness": 0.15,
                "accessibility": 0.15,
            },
            "min_acceptable_score": 50.0,
        },
    }

    # Conversión de enums a scores 0-5
    UPDATE_FREQ_SCORES = {
        "realtime": 5.0,
        "hourly": 4.5,
        "daily": 4.0,
        "weekly": 3.0,
        "monthly": 2.0,
        "quarterly": 1.0,
    }

    COVERAGE_SCORES = {
        "global": 5.0,
        "regional": 4.0,
        "national": 3.0,
        "local": 2.0,
    }

    @staticmethod
    def update_freq_to_score(freq: str) -> float:
        """Convierte UpdateFrequency a score 0-5."""
        return ReliabilityProfiler.UPDATE_FREQ_SCORES.get(freq.lower(), 2.0)

    @staticmethod
    def coverage_to_score(coverage: str) -> float:
        """Convierte Coverage a score 0-5."""
        return ReliabilityProfiler.COVERAGE_SCORES.get(coverage.lower(), 2.0)

    @staticmethod
    def calculate_composite_score(
        reliability: float,
        update_freq: str,
        coverage: str,
        completeness: float,
        accessibility: float,
        profile: str = "critical",
    ) -> float:
        """Calcula puntuación compuesta (0-100) con perfil especificado."""
        if profile not in ReliabilityProfiler.PROFILES:
            profile = "critical"

        weights = ReliabilityProfiler.PROFILES[profile]["weights"]

        # Convierte enums a scores
        freq_score = ReliabilityProfiler.update_freq_to_score(update_freq)
        cov_score = ReliabilityProfiler.coverage_to_score(coverage)

        # Escala completeness y accessibility a 0-5
        accessibility_score = accessibility * 5.0
        completeness_score = completeness * 5.0

        # Fórmula ponderada (suma ponderada de scores 0-5)
        composite = (
            (reliability * weights["reliability"])
            + (freq_score * weights["update_freq"])
            + (cov_score * weights["coverage"])
            + (completeness_score * weights["completeness"])
            + (accessibility_score * weights["accessibility"])
        )

        # Normaliza a 0-100 (suma ponderada de scores 0-5 da un máximo de 5)
        return round((composite / 5.0) * 100.0, 1)

    @staticmethod
    def assess_quality_tier(score: float) -> str:
        """Determina tier de calidad."""
        if score >= 90:
            return "excellent"
        elif score >= 75:
            return "very_good"
        elif score >= 60:
            return "good"
        else:
            return "acceptable"


def apply_profile(
    sources: list[dict[str, Any]], profile: str = "critical"
) -> list[dict[str, Any]]:
    """Aplica perfil a todas las fuentes y recalcula scores."""
    processed = []

    for source in sources:
        metrics = source.get("metrics", {})

        # Extrae componentes
        reliability = metrics.get("reliability", 3.0)
        update_freq = metrics.get("update_freq", "daily")
        coverage = metrics.get("coverage", "national")
        completeness = metrics.get("completeness", 0.75)
        accessibility = metrics.get("accessibility", 0.8)

        # Calcula nuevo score
        old_score = source.get("composite_score", 0)
        new_score = ReliabilityProfiler.calculate_composite_score(
            reliability=reliability,
            update_freq=update_freq,
            coverage=coverage,
            completeness=completeness,
            accessibility=accessibility,
            profile=profile,
        )

        # Actualiza fuente
        source["composite_score"] = new_score
        source["quality_tier"] = ReliabilityProfiler.assess_quality_tier(new_score)
        source["score_profile"] = profile
        source["score_change"] = round(new_score - old_score, 1)

        processed.append(source)

    return processed


def generate_report(sources: list[dict[str, Any]], profile: str = "critical") -> dict:
    """Genera reporte de cambios post-reweighting."""
    scores = [s["composite_score"] for s in sources]

    report = {
        "profile": profile,
        "profile_info": ReliabilityProfiler.PROFILES.get(profile, {}),
        "total_sources": len(sources),
        "score_statistics": {
            "min": min(scores) if scores else 0,
            "max": max(scores) if scores else 0,
            "mean": sum(scores) / len(sources) if sources else 0,
            "median": sorted(scores)[len(scores) // 2] if scores else 0,
        },
        "quality_distribution": {
            "excellent": len([s for s in sources if s["composite_score"] >= 90]),
            "very_good": len([s for s in sources if 75 <= s["composite_score"] < 90]),
            "good": len([s for s in sources if 60 <= s["composite_score"] < 75]),
            "acceptable": len([s for s in sources if s["composite_score"] < 60]),
        },
        "biggest_gainers": sorted(
            [s for s in sources if s.get("score_change", 0) > 0],
            key=lambda x: x["score_change"],
            reverse=True,
        )[:10],
        "biggest_losers": sorted(
            [s for s in sources if s.get("score_change", 0) < 0],
            key=lambda x: x["score_change"],
        )[:10],
    }

    return report


def main():
    input_file = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/sources-global-v2.json")
    output_file = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("data/sources-global-v2-critical.json")
    profile = sys.argv[3] if len(sys.argv) > 3 else "critical"

    if not input_file.exists():
        logger.error(f"❌ Archivo no encontrado: {input_file}")
        sys.exit(1)

    logger.info(f"📂 Leyendo: {input_file}")
    with open(input_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    sources = data.get("sources", [])
    logger.info(f"✓ Cargadas {len(sources)} fuentes")

    # Aplica perfil
    logger.info(f"\n🔄 Aplicando perfil '{profile}'...")
    reweighted = apply_profile(sources, profile=profile)

    # Genera reporte
    logger.info(f"📊 Generando reporte...")
    report = generate_report(reweighted, profile=profile)

    # Imprime reporte
    logger.info("\n" + "=" * 70)
    logger.info(f"PERFIL APLICADO: {report['profile_info'].get('name', profile)}")
    logger.info("=" * 70)

    desc = report["profile_info"].get("description", "")
    if desc:
        logger.info(f"\nDescripción: {desc}")

    logger.info(f"\nTotal fuentes reweightadas: {report['total_sources']}")

    logger.info(f"\n📈 DISTRIBUCIÓN DE CALIDAD:")
    dist = report["quality_distribution"]
    for tier in ["excellent", "very_good", "good", "acceptable"]:
        count = dist.get(tier, 0)
        pct = (count / report["total_sources"]) * 100 if report["total_sources"] > 0 else 0
        tier_name = {
            "excellent": "🟢 EXCELENTE (90-100)",
            "very_good": "🟡 MUY BUENO (75-89)",
            "good": "🟠 BUENO (60-74)",
            "acceptable": "🔴 ACEPTABLE (<60)",
        }
        logger.info(f"   {tier_name.get(tier, tier):30s} : {count:4d} ({pct:5.1f}%)")

    logger.info(f"\n📊 ESTADÍSTICAS:")
    stats = report["score_statistics"]
    logger.info(f"   Media  : {stats['mean']:6.1f}")
    logger.info(f"   Mediana: {stats['median']:6.1f}")
    logger.info(f"   Mínimo : {stats['min']:6.1f}")
    logger.info(f"   Máximo : {stats['max']:6.1f}")

    if report["biggest_gainers"]:
        logger.info(f"\n🔺 TOP 5 GANADORES (score subió):")
        for i, s in enumerate(report["biggest_gainers"][:5], 1):
            logger.info(f"   {i}. {s['name']:45s} {s['score_change']:+5.1f} → {s['composite_score']:5.0f}")

    if report["biggest_losers"]:
        logger.info(f"\n🔻 TOP 5 PERDEDORES (score bajó):")
        for i, s in enumerate(report["biggest_losers"][:5], 1):
            logger.info(f"   {i}. {s['name']:45s} {s['score_change']:+5.1f} → {s['composite_score']:5.0f}")

    # Guarda resultado
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_data = {
        "version": "2.0-critical",
        "generated": datetime.now().isoformat(),
        "profile": profile,
        "total": len(reweighted),
        "sources": reweighted,
        "report": report,
    }

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    logger.info(f"\n💾 Guardado: {output_file}")
    logger.info(f"✓ Reweighting completado")


if __name__ == "__main__":
    main()
