"""Observabilidad del pipeline: audit.etl_runs, audit.etl_run_tablas y watermark.

Se usa una conexión en modo autocommit propia, separada de la de carga:
así el registro del run queda guardado aunque la transacción de carga falle
y se revierta.
"""

import logging
import os
import re
import subprocess
from datetime import date

import psycopg

log = logging.getLogger(__name__)

FUENTE_OLIST = "olist_orders"
LARGO_MAX_ERROR = 2000


def detectar_origen() -> str:
    """'schedule' (cron), 'manual' (workflow_dispatch) o 'local'."""
    evento = os.getenv("GITHUB_EVENT_NAME", "")
    if evento == "schedule":
        return "schedule"
    if evento == "workflow_dispatch":
        return "manual"
    return "local"


def obtener_git_sha() -> str | None:
    """SHA del commit (GitHub Actions lo expone; en local se consulta a git)."""
    sha = os.getenv("GITHUB_SHA")
    if sha:
        return sha[:7]
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None


def sanitizar_error(mensaje: str) -> str:
    """Elimina credenciales de un mensaje de error antes de guardarlo o mostrarlo."""
    mensaje = re.sub(r"postgres(?:ql)?://[^\s'\"]+", "postgresql://***", mensaje)
    mensaje = re.sub(r"(password\s*=\s*)\S+", r"\1***", mensaje, flags=re.IGNORECASE)
    return mensaje[:LARGO_MAX_ERROR]


def iniciar_run(conn: psycopg.Connection, origen: str, git_sha: str | None) -> int:
    run_id = conn.execute(
        "INSERT INTO audit.etl_runs (origen, git_sha) VALUES (%s, %s) RETURNING run_id",
        (origen, git_sha),
    ).fetchone()[0]
    log.info("Run %d iniciado (origen=%s, git=%s)", run_id, origen, git_sha)
    return run_id


def registrar_tablas(
    conn: psycopg.Connection, run_id: int, conteos: dict[str, tuple[int, int]]
) -> None:
    """Guarda filas leídas/cargadas por tabla (upsert por run y tabla)."""
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO audit.etl_run_tablas (run_id, tabla, filas_leidas, filas_cargadas) "
            "VALUES (%s, %s, %s, %s) "
            "ON CONFLICT (run_id, tabla) DO UPDATE SET "
            "filas_leidas = EXCLUDED.filas_leidas, filas_cargadas = EXCLUDED.filas_cargadas",
            [(run_id, tabla, leidas, cargadas) for tabla, (leidas, cargadas) in conteos.items()],
        )


def finalizar_run(
    conn: psycopg.Connection,
    run_id: int,
    estado: str,
    desde: date | None = None,
    hasta: date | None = None,
    error: str | None = None,
    tests_ok: int | None = None,
    tests_fallidos: int | None = None,
) -> None:
    conn.execute(
        """
        UPDATE audit.etl_runs
           SET finalizado_en  = now(),
               duracion_seg   = round(extract(epoch FROM now() - iniciado_en)::numeric, 2),
               estado         = %s,
               ventana_desde  = %s,
               ventana_hasta  = %s,
               mensaje_error  = %s,
               tests_ok       = %s,
               tests_fallidos = %s
         WHERE run_id = %s
        """,
        (
            estado,
            desde,
            hasta,
            sanitizar_error(error) if error else None,
            tests_ok,
            tests_fallidos,
            run_id,
        ),
    )
    log.info("Run %d finalizado con estado '%s'", run_id, estado)


def leer_watermark(conn: psycopg.Connection, fuente: str = FUENTE_OLIST) -> date | None:
    fila = conn.execute(
        "SELECT ultima_fecha_cargada FROM control.watermark WHERE fuente = %s", (fuente,)
    ).fetchone()
    return fila[0] if fila else None


def actualizar_watermark(
    conn: psycopg.Connection, fecha: date, run_id: int, fuente: str = FUENTE_OLIST
) -> None:
    conn.execute(
        """
        INSERT INTO control.watermark (fuente, ultima_fecha_cargada, run_id, actualizado_en)
        VALUES (%s, %s, %s, now())
        ON CONFLICT (fuente) DO UPDATE
           SET ultima_fecha_cargada = EXCLUDED.ultima_fecha_cargada,
               run_id = EXCLUDED.run_id,
               actualizado_en = now()
        """,
        (fuente, fecha, run_id),
    )
    log.info("Watermark '%s' actualizado a %s", fuente, fecha)
