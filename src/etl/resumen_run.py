"""Imprime en Markdown el resumen del último run (para el Step Summary de GitHub Actions).

Uso:  python -m etl.resumen_run >> "$GITHUB_STEP_SUMMARY"

Solo muestra datos de audit.etl_runs / etl_run_tablas (sin credenciales).
"""

import sys

from etl.db import conectar


def generar_resumen(conn) -> str:
    run = conn.execute(
        """
        SELECT run_id, estado, origen, ventana_desde, ventana_hasta, duracion_seg,
               tests_ok, tests_fallidos, mensaje_error
        FROM audit.etl_runs ORDER BY run_id DESC LIMIT 1
        """
    ).fetchone()
    if run is None:
        return "Sin ejecuciones registradas en audit.etl_runs.\n"

    run_id, estado, origen, desde, hasta, duracion, ok, fallidos, error = run
    icono = {"exito": "✅", "sin_datos": "⏸️", "fallido": "❌"}.get(estado, "⏳")
    watermark = conn.execute(
        "SELECT ultima_fecha_cargada FROM control.watermark WHERE fuente = 'olist_orders'"
    ).fetchone()

    lineas = [
        f"## {icono} Run {run_id}: {estado}",
        "",
        "| Campo | Valor |",
        "|---|---|",
        f"| Origen | {origen} |",
        f"| Ventana | {desde or '-'} → {hasta or '-'} |",
        f"| Duración | {duracion or '-'} s |",
        f"| Tests dbt OK / fallidos | {ok if ok is not None else '-'} / "
        f"{fallidos if fallidos is not None else '-'} |",
        f"| Watermark actual | {watermark[0] if watermark else '-'} |",
    ]
    if error:
        lineas += ["", f"**Error:** `{error[:500]}`"]

    tablas = conn.execute(
        "SELECT tabla, filas_leidas, filas_cargadas FROM audit.etl_run_tablas "
        "WHERE run_id = %s ORDER BY tabla",
        (run_id,),
    ).fetchall()
    if tablas:
        lineas += ["", "| Tabla | Filas leídas | Filas cargadas |", "|---|---:|---:|"]
        lineas += [f"| {t} | {leidas:,} | {cargadas:,} |" for t, leidas, cargadas in tablas]
    return "\n".join(lineas) + "\n"


def main() -> int:
    # Los íconos (✅ ❌) requieren UTF-8 aunque la salida se redirija a un archivo
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    with conectar(autocommit=True) as conn:
        sys.stdout.write(generar_resumen(conn))
    return 0


if __name__ == "__main__":
    sys.exit(main())
