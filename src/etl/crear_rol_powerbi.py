"""Crea (o actualiza) el rol de solo lectura `powerbi_lector`.

- Solo puede LEER el esquema `reporting` (ni raw, ni marts, ni audit directamente).
- La contraseña se genera aleatoriamente y se guarda en `.env` (ignorado por git)
  como POWERBI_LECTOR_PASSWORD. Nunca se imprime en consola.
- Si la variable ya existe en `.env`, se reutiliza (idempotente).

Uso:  python -m etl.crear_rol_powerbi
"""

import logging
import os
import secrets
import sys

from dotenv import set_key
from psycopg import sql

from etl.config import RAIZ_PROYECTO
from etl.db import conectar
from etl.logging_config import configurar_logging

log = logging.getLogger("etl.crear_rol_powerbi")

ROL = "powerbi_lector"
VAR_PASSWORD = "POWERBI_LECTOR_PASSWORD"
ARCHIVO_ENV = RAIZ_PROYECTO / ".env"


def _obtener_o_generar_password() -> str:
    """Reutiliza la contraseña de .env o genera una nueva (alta entropía)."""
    existente = os.getenv(VAR_PASSWORD, "").strip()
    if existente:
        log.info("Reutilizando contraseña existente de %s", VAR_PASSWORD)
        return existente
    nueva = secrets.token_urlsafe(24)  # ~192 bits de entropía
    ARCHIVO_ENV.touch(exist_ok=True)
    set_key(str(ARCHIVO_ENV), VAR_PASSWORD, nueva, quote_mode="never")
    log.info("Contraseña nueva generada y guardada en .env (%s)", VAR_PASSWORD)
    return nueva


def main() -> int:
    configurar_logging()
    password = _obtener_o_generar_password()
    rol = sql.Identifier(ROL)

    with conectar() as conn:
        existe = conn.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (ROL,)).fetchone()
        accion = "ALTER" if existe else "CREATE"
        conn.execute(
            sql.SQL("{} ROLE {} WITH LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB NOCREATEROLE").format(
                sql.SQL(accion), rol, sql.Literal(password)
            )
        )
        db = conn.execute("SELECT current_database()").fetchone()[0]
        propietario = conn.execute("SELECT current_user").fetchone()[0]

        # Permisos mínimos: conectarse y leer solo el esquema reporting
        sentencias = [
            sql.SQL("REVOKE ALL ON DATABASE {} FROM {}").format(sql.Identifier(db), rol),
            sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(sql.Identifier(db), rol),
            sql.SQL("REVOKE ALL ON SCHEMA public FROM {}").format(rol),
            sql.SQL("GRANT USAGE ON SCHEMA reporting TO {}").format(rol),
            sql.SQL("GRANT SELECT ON ALL TABLES IN SCHEMA reporting TO {}").format(rol),
            # Las vistas que dbt cree después en reporting también serán legibles
            sql.SQL(
                "ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA reporting "
                "GRANT SELECT ON TABLES TO {}"
            ).format(sql.Identifier(propietario), rol),
            # Evita que el rol se quede con consultas colgadas consumiendo cómputo
            sql.SQL("ALTER ROLE {} SET statement_timeout = '120s'").format(rol),
        ]
        for sentencia in sentencias:
            conn.execute(sentencia)
        conn.commit()

    log.info(
        "Rol %s %s con acceso de solo lectura a 'reporting'",
        ROL,
        "actualizado" if existe else "creado",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
