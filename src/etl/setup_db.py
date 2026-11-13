"""Crea esquemas y tablas base (sql/setup/*.sql). Es idempotente.

Uso:  python -m etl.setup_db
"""

import logging
import sys

from etl.config import RAIZ_PROYECTO
from etl.db import conectar, ejecutar_archivo_sql
from etl.logging_config import configurar_logging

log = logging.getLogger("etl.setup_db")
DIR_SETUP = RAIZ_PROYECTO / "sql" / "setup"


def main() -> int:
    configurar_logging()
    archivos = sorted(DIR_SETUP.glob("*.sql"))
    if not archivos:
        log.error("No se encontraron scripts en %s", DIR_SETUP)
        return 1

    # Todo en una sola transacción: o se aplica completo o nada
    with conectar() as conn:
        for archivo in archivos:
            ejecutar_archivo_sql(conn, archivo)
        conn.commit()
    log.info("Setup aplicado correctamente (%d scripts)", len(archivos))
    return 0


if __name__ == "__main__":
    sys.exit(main())
