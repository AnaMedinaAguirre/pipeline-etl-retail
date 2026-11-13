"""Prueba de conexión a Neon sin exponer credenciales.

Verifica:
  1. Conexión con el rol propietario (la que usan el pipeline y dbt).
  2. Esquemas y tablas base creadas.
  3. Conexión con el rol powerbi_lector y que NO pueda leer fuera de reporting.

Uso:  python -m etl.probar_conexion
"""

import logging
import os
import sys
from urllib.parse import quote, urlparse, urlunparse

import psycopg

from etl.config import obtener_database_url
from etl.db import conectar
from etl.logging_config import configurar_logging

log = logging.getLogger("etl.probar_conexion")

ESQUEMAS_ESPERADOS = {"raw", "staging", "intermediate", "marts", "reporting", "control", "audit"}


def _url_con_usuario(url: str, usuario: str, password: str) -> str:
    """Reemplaza usuario/contraseña de una URL de Postgres."""
    p = urlparse(url)
    netloc = f"{quote(usuario)}:{quote(password, safe='')}@{p.hostname}"
    if p.port:
        netloc += f":{p.port}"
    return urlunparse(p._replace(netloc=netloc))


def probar_propietario() -> bool:
    with conectar() as conn:
        version = conn.execute("SHOW server_version").fetchone()[0]
        # SSL visto desde el cliente: en Neon el TLS lo termina su proxy,
        # por eso pg_stat_ssl del servidor no sirve para esta verificación.
        ssl = conn.pgconn.ssl_in_use
        esquemas = {
            fila[0]
            for fila in conn.execute(
                "SELECT schema_name FROM information_schema.schemata"
            ).fetchall()
        }
        tablas = conn.execute(
            "SELECT count(*) FROM information_schema.tables "
            "WHERE table_schema IN ('control','audit')"
        ).fetchone()[0]

    log.info("Postgres %s | SSL activo: %s", version, ssl)
    faltantes = ESQUEMAS_ESPERADOS - esquemas
    if faltantes:
        log.error("Faltan esquemas: %s (ejecuta python -m etl.setup_db)", sorted(faltantes))
        return False
    log.info("Esquemas OK: %s", ", ".join(sorted(ESQUEMAS_ESPERADOS)))
    log.info("Tablas en control/audit: %d", tablas)
    return bool(ssl)


def probar_powerbi_lector() -> bool:
    password = os.getenv("POWERBI_LECTOR_PASSWORD", "").strip()
    if not password:
        log.warning(
            "POWERBI_LECTOR_PASSWORD no definida: se omite (python -m etl.crear_rol_powerbi)"
        )
        return True

    url = _url_con_usuario(obtener_database_url(), "powerbi_lector", password)
    with conectar(url=url, autocommit=True) as conn:
        filas = conn.execute("SELECT usuario FROM reporting.vw_prueba_conexion").fetchall()
        log.info("powerbi_lector lee reporting.vw_prueba_conexion: %d fila(s)", len(filas))
        try:
            conn.execute("SELECT 1 FROM audit.etl_runs LIMIT 1")
        except psycopg.errors.InsufficientPrivilege:
            log.info("powerbi_lector NO puede leer audit.etl_runs directamente (correcto)")
            return True
    log.error("powerbi_lector pudo leer fuera de 'reporting': revisar permisos")
    return False


def main() -> int:
    configurar_logging()
    ok = probar_propietario() and probar_powerbi_lector()
    log.info("RESULTADO: %s", "CONEXIÓN OK" if ok else "HAY PROBLEMAS")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
