"""Utilidades de conexión a PostgreSQL (Neon)."""

import logging
from pathlib import Path

import psycopg

from etl.config import describir_conexion, obtener_database_url

log = logging.getLogger(__name__)


def conectar(autocommit: bool = False, url: str | None = None) -> psycopg.Connection:
    """Abre una conexión a Postgres. Exige SSL (Neon lo requiere)."""
    url = url or obtener_database_url()
    log.info("Conectando a Postgres (%s)", describir_conexion(url))
    # connect_timeout amplio: Neon puede tardar unos segundos en "despertar" (scale to zero)
    return psycopg.connect(url, autocommit=autocommit, connect_timeout=30, sslmode="require")


def ejecutar_archivo_sql(conn: psycopg.Connection, ruta: Path) -> None:
    """Ejecuta un archivo .sql completo dentro de la transacción actual."""
    log.info("Ejecutando %s", ruta.name)
    conn.execute(ruta.read_text(encoding="utf-8"))
