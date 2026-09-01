#!/usr/bin/env python3
"""Crea el esquema de base de datos.

    python scripts/init_db.py                    # usa DATABASE_URL del .env
    python scripts/init_db.py --url sqlite:///x.db
    python scripts/init_db.py --drop             # borra y recrea (destructivo)
"""

from __future__ import annotations

import argparse
import sys

from engine import database
from engine.config import get_settings
from engine.models import Base


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", help="URL de la base de datos; por defecto, la del .env")
    parser.add_argument(
        "--drop",
        action="store_true",
        help="borra todas las tablas antes de crearlas (DESTRUCTIVO)",
    )
    args = parser.parse_args(argv)

    url = args.url or get_settings().database_url
    engine = database.configure(url)

    # No se muestra la URL entera: puede llevar la contraseña de PostgreSQL.
    safe_url = url.split("@")[-1] if "@" in url else url
    print(f"Base de datos: {safe_url}")

    if args.drop:
        respuesta = input("Esto BORRARÁ todas las tablas y sus datos. Escribe 'si': ")
        if respuesta.strip().lower() != "si":
            print("Cancelado.")
            return 1
        Base.metadata.drop_all(bind=engine)
        print("Tablas eliminadas.")

    database.init_db(engine)
    print(f"Esquema listo: {', '.join(sorted(Base.metadata.tables))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
