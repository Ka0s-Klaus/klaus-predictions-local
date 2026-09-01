#!/usr/bin/env python3
"""Genera `docs/FEEDS.md` a partir del catálogo.

Escribir la tabla a mano garantizaría que se desincronice del YAML en la
segunda fuente que se añada.

    python scripts/gen_feeds_doc.py            # escribe docs/FEEDS.md
    python scripts/gen_feeds_doc.py --check    # falla si está desactualizado
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from engine.feeds import implemented_entries, load_catalog, planned_entries, summary

DEST = Path(__file__).resolve().parent.parent / "docs" / "FEEDS.md"


def render() -> str:
    datos = summary()
    lineas: list[str] = [
        "<!-- Generado por scripts/gen_feeds_doc.py. No editar a mano. -->",
        "",
        "# Catálogo de fuentes",
        "",
        f"**{datos['total']} fuentes declaradas** · {datos['implemented']} implementadas · "
        f"{datos['planned']} pendientes · {datos['requires_key']} requieren clave de API.",
        "",
        "La fuente de verdad es [`engine/feeds/catalog.yaml`]"
        "(../engine/feeds/catalog.yaml). Este fichero se genera a partir de él.",
        "",
        "## Implementadas",
        "",
        "Cada una tiene una clase en `engine/feeds/sources/` y su endpoint se ha",
        "comprobado contra el servicio real.",
        "",
        "| Fuente | Dominio | Qué aporta |",
        "| ------ | ------- | ---------- |",
    ]

    for entry in implemented_entries():
        nombre = f"[{entry.name}]({entry.homepage})" if entry.homepage else entry.name
        lineas.append(f"| {nombre} | `{entry.domain}` | {entry.description} |")

    lineas += [
        "",
        "## Pendientes",
        "",
        "Fuentes identificadas y sin implementar. **No llevan endpoint**: la ruta de",
        "cada API vive en la clase que la consume, así que apuntarla aquí sólo",
        "crearía un segundo sitio que mantener. Lo que sí llevan es el enlace al",
        "servicio y, cuando lo hay, el obstáculo concreto que queda por resolver.",
        "",
        "| Fuente | Dominio | Clave | Notas |",
        "| ------ | ------- | ----- | ----- |",
    ]

    for entry in planned_entries():
        nombre = f"[{entry.name}]({entry.homepage})" if entry.homepage else entry.name
        clave = "sí" if entry.requires_key else "—"
        nota = " ".join((entry.notes or entry.description).split())
        lineas.append(f"| {nombre} | `{entry.domain}` | {clave} | {nota} |")

    lineas += [
        "",
        "## Por dominio",
        "",
        "| Dominio | Fuentes |",
        "| ------- | ------- |",
    ]
    for dominio, n in datos["by_domain"].items():
        lineas.append(f"| `{dominio}` | {n} |")

    lineas += [
        "",
        "## Añadir una fuente",
        "",
        "1. Crea la clase en `engine/feeds/sources/`, heredando de `FeedSource`.",
        "   Sólo hay que definir `name`, `domain`, `event_type`, `endpoint` y",
        "   `parse()`; la concurrencia, los tiempos de espera y la deduplicación",
        "   los pone el ingestor.",
        "2. Regístrala en `IMPLEMENTATIONS`, en `engine/feeds/sources/__init__.py`.",
        "3. Cambia su `status` a `implemented` en `catalog.yaml`.",
        "4. Añade un test del parser en `tests/test_feeds.py` con una respuesta",
        "   real recortada del servicio.",
        "5. Regenera este fichero: `python scripts/gen_feeds_doc.py`.",
        "",
        "El registro valida el cruce al arrancar: declarar una fuente como",
        "implementada sin clase detrás —o al revés— es un error inmediato, no un",
        "fallo silencioso a mitad de la ingesta.",
        "",
        "## Sobre la relevancia",
        "",
        "Cada fuente calcula su propia `salience` entre 0 y 1, y es lo que decide",
        "qué llega al contexto del enjambre. Los criterios son específicos de cada",
        "una: magnitud y profundidad en un sismo, escala NOAA en una alerta de",
        "clima espacial, léxico de escalada en un titular. Los tipos de cambio",
        "puntúan bajo a propósito — son contexto, no sucesos, y no deben desplazar",
        "a un terremoto.",
        "",
        "## Términos de uso",
        "",
        "Todas son APIs públicas de terceros con sus propios límites de peticiones",
        "y condiciones. Consúltalas antes de desplegar nada en producción. GDELT en",
        "particular limita con dureza y falla con cierta frecuencia; el ingestor",
        "está diseñado para tolerarlo.",
        "",
    ]
    return "\n".join(lineas)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="sólo comprobar, no escribir")
    args = parser.parse_args(argv)

    contenido = render()

    if args.check:
        actual = DEST.read_text(encoding="utf-8") if DEST.exists() else ""
        if actual != contenido:
            print("docs/FEEDS.md está desactualizado. Ejecuta scripts/gen_feeds_doc.py")
            return 1
        print("docs/FEEDS.md al día")
        return 0

    DEST.parent.mkdir(parents=True, exist_ok=True)
    DEST.write_text(contenido, encoding="utf-8")
    print(f"Escrito {DEST} ({len(load_catalog())} fuentes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
