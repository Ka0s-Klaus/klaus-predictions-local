#!/usr/bin/env python3
"""
Parser: Markdown Pythia v2.0 → JSON de fuentes.

Extrae tablas de fuentes del markdown y genera JSON estructurado
compatible con el catálogo de Klaus.

Uso:
  python scripts/parse_pythia_sources.py \\
    /path/to/fuentes-globales-completa-v2.md \\
    data/sources-global-v2.json
"""

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Mapeos de emojis/texto a valores estructurados
TOPIC_MAP = {
    "🌧️": "weather",
    "🗺️": "geopolitical",
    "🎓": "education",
    "🔒": "cybersecurity",
    "💹": "markets",
    "🌱": "sustainability",
    "💻": "technology",
    "⚡": "energy",
    "🏥": "health",
    "🚚": "trade",
    "🛰️": "geospatial",
}

ACCESS_TYPE_MAP = {
    "🌐": "web",
    "WEB": "web",
    "🔌": "api",
    "API": "api",
    "📡": "rss",
    "RSS": "rss",
    "RSS/FEED": "rss",
    "💾": "data_portal",
    "DATA": "data_portal",
    "DATA PORTAL": "data_portal",
    "📊": "dashboard",
    "DASHBOARD": "dashboard",
    "🔐": "registered",
    "REGISTRADO": "registered",
}

COUNTRY_MAP = {
    "ESPAÑA": "ES",
    "Spain": "ES",
    "FRANCIA": "FR",
    "France": "FR",
    "ALEMANIA": "DE",
    "Germany": "DE",
    "REINO UNIDO": "GB",
    "United Kingdom": "GB",
    "ITALIA": "IT",
    "Italy": "IT",
    "POLONIA": "PL",
    "Poland": "PL",
    "SUECIA": "SE",
    "Sweden": "SE",
    "SUIZA": "CH",
    "Switzerland": "CH",
    "PAÍSES BAJOS": "NL",
    "Netherlands": "NL",
    "BÉLGICA": "BE",
    "Belgium": "BE",
    "AUSTRIA": "AT",
    "Austria": "AT",
    "REPÚBLICA CHECA": "CZ",
    "Czech Republic": "CZ",
    "GRECIA": "GR",
    "Greece": "GR",
    "PORTUGAL": "PT",
    "Portugal": "PT",
    "ESTADOS UNIDOS": "US",
    "USA": "US",
    "CANADÁ": "CA",
    "Canada": "CA",
    "MÉXICO": "MX",
    "Mexico": "MX",
    "ARGENTINA": "AR",
    "Argentina": "AR",
    "BRASIL": "BR",
    "Brazil": "BR",
    "CHILE": "CL",
    "Chile": "CL",
    "COLOMBIA": "CO",
    "Colombia": "CO",
    "PERÚ": "PE",
    "Peru": "PE",
    "JAPÓN": "JP",
    "Japan": "JP",
    "CHINA": "CN",
    "China": "CN",
    "INDIA": "IN",
    "India": "IN",
    "COREA DEL SUR": "KR",
    "South Korea": "KR",
    "SINGAPUR": "SG",
    "Singapore": "SG",
    "TAILANDIA": "TH",
    "Thailand": "TH",
    "INDONESIA": "ID",
    "Indonesia": "ID",
    "FILIPINAS": "PH",
    "Philippines": "PH",
    "VIETNAM": "VN",
    "Vietnam": "VN",
    "MALASIA": "MY",
    "Malaysia": "MY",
    "IRÁN": "IR",
    "Iran": "IR",
    "TURQUÍA": "TR",
    "Turkey": "TR",
    "PAKISTÁN": "PK",
    "Pakistan": "PK",
    "BANGLADESH": "BD",
    "Bangladesh": "BD",
    "SUDÁFRICA": "ZA",
    "South Africa": "ZA",
    "EGIPTO": "EG",
    "Egypt": "EG",
    "NIGERIA": "NG",
    "Nigeria": "NG",
    "KENIA": "KE",
    "Kenya": "KE",
    "AUSTRALIA": "AU",
    "Australia": "AU",
    "NUEVA ZELANDA": "NZ",
    "New Zealand": "NZ",
}


def extract_reliability_stars(reliability_str: str) -> float:
    """Extrae número de estrellas (⭐) y convierte a 0-5."""
    stars = reliability_str.count("⭐")
    return float(stars) if 0 <= stars <= 5 else 3.0


def extract_score(score_str: str) -> float:
    """Extrae puntuación numérica del string."""
    match = re.search(r"(\d+(?:\.\d+)?)", score_str)
    return float(match.group(1)) if match else 75.0


def extract_update_freq(freq_str: str) -> str:
    """Convierte string de frecuencia a enum normalizado."""
    freq_lower = freq_str.lower()

    if "real-time" in freq_lower or "realtime" in freq_lower:
        return "realtime"
    elif "hourly" in freq_lower or "hora" in freq_lower:
        return "hourly"
    elif "diario" in freq_lower or "daily" in freq_lower:
        return "daily"
    elif "semanal" in freq_lower or "weekly" in freq_lower:
        return "weekly"
    elif "mensual" in freq_lower or "monthly" in freq_lower:
        return "monthly"
    elif "trimestral" in freq_lower or "quarterly" in freq_lower:
        return "quarterly"
    else:
        return "daily"


def extract_coverage(cov_str: str) -> str:
    """Convierte string de cobertura a enum normalizado."""
    cov_lower = cov_str.lower()

    if "global" in cov_lower:
        return "global"
    elif "regional" in cov_lower:
        return "regional"
    elif "nacional" in cov_lower or "national" in cov_lower:
        return "national"
    else:
        return "national"


def extract_access_type(access_str: str) -> str:
    """Convierte string de tipo de acceso a enum normalizado."""
    access_upper = access_str.upper()

    for key, value in ACCESS_TYPE_MAP.items():
        if key in access_upper:
            return value

    return "web"


def assess_quality_tier(score: float) -> str:
    """Determina tier de calidad basado en score."""
    if score >= 90:
        return "excellent"
    elif score >= 75:
        return "very_good"
    elif score >= 60:
        return "good"
    else:
        return "acceptable"


def map_to_klaus_domain(topic: str) -> str:
    """Mapea tema Pythia a dominio Klaus."""
    topic_lower = topic.lower()

    domain_mappings = {
        "weather": "weather",
        "climate": "climate",
        "meteorology": "weather",
        "geopolitical": "geopolitical",
        "geopolitics": "geopolitical",
        "conflict": "geopolitical",
        "cybersecurity": "cyber",
        "cyber": "cyber",
        "markets": "markets",
        "bolsas": "markets",
        "sustainability": "climate",
        "energy": "energy",
        "health": "health",
        "salud": "health",
        "trade": "trade",
        "comercio": "trade",
        "technology": "technology",
        "tecnología": "technology",
        "education": "technology",
        "geospatial": "infrastructure",
        "inteligencia": "infrastructure",
        "desastres": "disasters",
        "disasters": "disasters",
    }

    for key, domain in domain_mappings.items():
        if key in topic_lower:
            return domain

    return "technology"


class PythiaSourceParser:
    """Parser del markdown Pythia v2.0."""

    def __init__(self, md_file: Path):
        self.md_file = md_file
        self.content = md_file.read_text(encoding="utf-8")
        self.current_country = "GLOBAL"
        self.current_topic = "general"
        self.sources: list[dict[str, Any]] = []

    def parse(self) -> list[dict[str, Any]]:
        """Extrae todas las fuentes del markdown."""
        lines = self.content.split("\n")

        for i, line in enumerate(lines):
            # Actualiza país actual
            if line.startswith("## 🇪🇸 ") or re.match(r"^## 🇪🇸 ", line):
                self._extract_country(line)

            # Actualiza tema actual
            if line.startswith("### "):
                self._extract_topic(line)

            # Busca tabla de fuentes
            if line.startswith("| Fuente |"):
                self._parse_table(lines, i)

        logger.info(f"✓ Extraídas {len(self.sources)} fuentes")
        return self.sources

    def _extract_country(self, line: str) -> None:
        """Extrae código de país de línea de encabezado."""
        # Busca patrón: ## 🇪🇸 PAIS
        match = re.search(
            r"## 🇪🇸 ([A-Z]{2}|[A-Za-z\s]+)(?:\s|\(|$)", line
        )
        if match:
            country_text = match.group(1).strip()
            # Intenta mapeo, si no usa el texto como-es
            self.current_country = COUNTRY_MAP.get(
                country_text.upper(), country_text.upper()[:2]
            )
            logger.debug(f"País: {self.current_country}")

    def _extract_topic(self, line: str) -> None:
        """Extrae tema de línea de encabezado subsección."""
        # Busca emoji al inicio: ### 🌧️ Meteorología
        for emoji, topic in TOPIC_MAP.items():
            if emoji in line:
                self.current_topic = topic
                logger.debug(f"Tema: {self.current_topic}")
                break

    def _parse_table(self, lines: list[str], start: int) -> None:
        """Parsea tabla a partir de línea start."""
        i = start + 1  # Salta línea de separador
        while i < len(lines):
            line = lines[i].strip()
            i += 1

            # Fin de tabla (línea en blanco o nuevo encabezado)
            if not line or line.startswith("#"):
                break

            # Salta línea de separador (----)
            if "---" in line:
                continue

            # Parsea fila de tabla
            if line.startswith("|") and line.endswith("|"):
                self._parse_row(line)

    def _parse_row(self, row: str) -> None:
        """Extrae una fuente de una fila de tabla."""
        # Formato: | Name | URL | Fiabilidad | Actualización | Cobertura | Acceso | Score |
        cells = [cell.strip() for cell in row.split("|")[1:-1]]

        if len(cells) < 7:
            return

        try:
            name = cells[0]
            url = cells[1]
            reliability_str = cells[2]
            update_freq_str = cells[3]
            coverage_str = cells[4]
            access_str = cells[5]
            score_str = cells[6]

            # Limpia emojis y espacios
            name = re.sub(r"^[\*\*]+", "", name).strip()
            url = url.strip()

            # Salta encabezados
            if name.lower() == "fuente" or not url.startswith("http"):
                return

            # Extrae scores
            reliability = extract_reliability_stars(reliability_str)  # Estrellas 0-5
            score = extract_score(score_str)  # Puntuación 0-100
            update_freq = extract_update_freq(update_freq_str)
            coverage = extract_coverage(coverage_str)
            access_type = extract_access_type(access_str)

            # Determina completeness y accessibility
            completeness = 1.0 if coverage != "local" else 0.75
            accessibility = 1.0 if access_type == "web" else 0.8

            source = {
                "id": f"{self.current_country.lower()}-{re.sub(r'[^a-z0-9]', '', name.lower())}-{len(self.sources):05d}",
                "name": name,
                "url": url,
                "country": self.current_country,
                "domain": map_to_klaus_domain(self.current_topic),
                "topic": self.current_topic,
                "access_type": access_type,
                "metrics": {
                    "reliability": reliability,
                    "update_freq": update_freq,
                    "coverage": coverage,
                    "completeness": completeness,
                    "accessibility": accessibility,
                    "years_active": 10,
                },
                "composite_score": score,
                "quality_tier": assess_quality_tier(score),
                "is_active": True,
                "parser_type": "html"
                if access_type == "web"
                else "json"
                if access_type == "api"
                else "rss" if access_type == "rss" else "html",
                "tags": [
                    "global-sources-v2",
                    self.current_country.lower(),
                    self.current_topic,
                ],
                "source_profile": "balanced",
            }

            self.sources.append(source)
            logger.debug(f"✓ {name} ({self.current_country})")

        except Exception as e:
            logger.warning(f"Error parseando fila '{row}': {e}")


def main():
    import sys

    md_file = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/FUENTES-README.md")
    output_file = Path(
        sys.argv[2]
    ) if len(sys.argv) > 2 else Path("data/sources-global-v2.json")

    if not md_file.exists():
        logger.error(f"❌ Archivo no encontrado: {md_file}")
        sys.exit(1)

    logger.info(f"📂 Parseando: {md_file}")
    parser = PythiaSourceParser(md_file)
    sources = parser.parse()

    # Estadísticas
    by_country = {}
    by_domain = {}
    by_quality = {}

    for s in sources:
        country = s["country"]
        domain = s["domain"]
        quality = s["quality_tier"]

        by_country[country] = by_country.get(country, 0) + 1
        by_domain[domain] = by_domain.get(domain, 0) + 1
        by_quality[quality] = by_quality.get(quality, 0) + 1

    # Guarda resultado
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_data = {
        "version": "2.0",
        "generated": datetime.now().isoformat(),
        "total": len(sources),
        "by_country": dict(sorted(by_country.items())),
        "by_domain": dict(sorted(by_domain.items())),
        "by_quality": dict(sorted(by_quality.items())),
        "sources": sources,
    }

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    logger.info(f"\n✓ Resultado guardado: {output_file}")
    logger.info(f"\n📊 Estadísticas:")
    logger.info(f"  Total fuentes: {len(sources)}")
    logger.info(f"  Países: {len(by_country)}")
    logger.info(f"  Dominios: {len(by_domain)}")
    logger.info(f"\n  Por calidad:")
    for quality in sorted(by_quality.keys()):
        count = by_quality[quality]
        pct = (count / len(sources)) * 100
        logger.info(f"    {quality}: {count} ({pct:.1f}%)")

    logger.info(f"\n  Top 5 países:")
    for country in sorted(by_country.keys(), key=lambda x: by_country[x], reverse=True)[
        :5
    ]:
        logger.info(f"    {country}: {by_country[country]}")


if __name__ == "__main__":
    main()
