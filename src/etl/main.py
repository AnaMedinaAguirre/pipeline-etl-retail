"""Orquestador del pipeline.

Pasos de cada ejecución:
  1. Registrar el inicio en audit.etl_runs.
  2. Extract Olist: descargar (si hace falta) y leer los CSV.
  3. Calcular la ventana del simulador a partir del watermark.
  4. Extract tipos de cambio (BCB y BCRP) para la ventana.
  5. Load raw: Olist + tipos de cambio en UNA transacción (idempotente).
  6. Transform + tests de calidad con `dbt build`. Si un test falla, el run falla.
  7. Avanzar el watermark (solo si todo lo anterior terminó bien) y cerrar el run.

Uso:
  python -m etl.main               # siguiente lote según el watermark
  python -m etl.main --dias 30     # este run recibe 30 días en vez de BATCH_DAYS
  python -m etl.main --dry-run     # muestra la ventana y las filas, sin cargar nada
"""

import argparse
import logging
import sys
import time
from datetime import timedelta

from etl import audit, extract_fx, extract_olist, load_raw
from etl.config import cargar_config
from etl.db import conectar
from etl.dbt_cli import ResultadoDbt, ejecutar_dbt
from etl.logging_config import configurar_logging
from etl.simulador import Ventana, calcular_ventana, extraer_lote, rango_de_datos

log = logging.getLogger("etl.main")

# Días hacia atrás que se piden de tipo de cambio antes de la ventana, para que
# el primer día de la ventana tenga una tasa previa con la cual rellenar si cae
# en fin de semana o feriado.
DIAS_PREVIOS_FX = 15


class DbtFallido(RuntimeError):
    """dbt build terminó con modelos o tests fallidos."""

    def __init__(self, resumen: ResultadoDbt):
        self.resumen = resumen
        super().__init__(
            f"dbt build falló: {resumen.tests_fallidos} test(s) fallido(s), "
            f"{resumen.modelos_error} modelo(s) con error"
        )


class Paso:
    """Context manager que mide y registra la duración de cada paso."""

    def __init__(self, nombre: str):
        self.nombre = nombre

    def __enter__(self):
        self.inicio = time.perf_counter()
        log.info("▶ %s", self.nombre)
        return self

    def __exit__(self, tipo_exc, *_):
        seg = time.perf_counter() - self.inicio
        if tipo_exc is None:
            log.info("✔ %s (%.1f s)", self.nombre, seg)
        else:
            log.error("✖ %s falló tras %.1f s", self.nombre, seg)
        return False


def extraer_tipos_de_cambio(ventana: Ventana) -> dict[str, list]:
    """Descarga las series diarias y la mensual de validación para la ventana."""
    fx_desde = ventana.desde - timedelta(days=DIAS_PREVIOS_FX)
    return {
        "diario": extract_fx.obtener_bcb(extract_fx.SERIE_BCB_USD_BRL, fx_desde, ventana.hasta)
        + extract_fx.obtener_bcrp(extract_fx.SERIE_BCRP_PEN_USD, fx_desde, ventana.hasta),
        "mensual": extract_fx.obtener_bcrp(
            extract_fx.SERIE_BCRP_BRL_USD_MENSUAL, fx_desde, ventana.hasta, mensual=True
        ),
    }


def ejecutar(dias_override: int | None = None, dry_run: bool = False) -> int:
    cfg = cargar_config()
    origen = audit.detectar_origen()

    if dry_run:
        return _dry_run(cfg, dias_override)

    with conectar(autocommit=True) as conn_audit:
        run_id = audit.iniciar_run(conn_audit, origen, audit.obtener_git_sha())
        ventana = None
        try:
            with Paso("Extract Olist"):
                directorio = cfg.dir_datos / "olist"
                extract_olist.descargar_dataset(directorio)
                datos = extract_olist.leer_dataset(directorio)
                fecha_min, fecha_max = rango_de_datos(datos["orders"])
                log.info("Pedidos disponibles en el dataset: %s → %s", fecha_min, fecha_max)

            with Paso("Calcular ventana del simulador"):
                watermark = audit.leer_watermark(conn_audit)
                log.info("Watermark actual: %s", watermark or "sin cargas previas")
                ventana = calcular_ventana(
                    watermark,
                    fecha_min,
                    fecha_max,
                    cfg.batch_days,
                    cfg.fecha_carga_inicial,
                    dias_override,
                )

            if ventana is None:
                log.info("No hay datos nuevos: el dataset ya se cargó completo hasta %s", fecha_max)
                audit.finalizar_run(conn_audit, run_id, "sin_datos")
                return 0
            log.info("Ventana a cargar: %s", ventana)

            with Paso("Filtrar lote"):
                lote = extraer_lote(datos, ventana)
                log.info("Pedidos en el lote: %d", len(lote["orders"]))

            with Paso("Extract tipos de cambio (BCB, BCRP)"):
                fx = extraer_tipos_de_cambio(ventana)

            with Paso("Load raw (transacción única)"):
                with conectar() as conn_carga:
                    conteos = load_raw.cargar_lote_olist(
                        conn_carga, lote, run_id, ventana.desde, ventana.hasta
                    )
                    n_diario = load_raw.cargar_tipo_cambio(conn_carga, fx["diario"], run_id)
                    n_mensual = load_raw.cargar_tipo_cambio(
                        conn_carga, fx["mensual"], run_id, mensual=True
                    )
                    conn_carga.commit()
                conteos["raw.tipo_cambio_diario"] = (len(fx["diario"]), n_diario)
                conteos["raw.tipo_cambio_mensual"] = (len(fx["mensual"]), n_mensual)
                audit.registrar_tablas(conn_audit, run_id, conteos)

            with Paso("Transform + tests de calidad (dbt build)"):
                dbt = ejecutar_dbt(["build"])
                log.info(
                    "dbt: tests OK=%d, advertencias=%d, fallidos=%d | modelos OK=%d, con error=%d",
                    dbt.tests_ok,
                    dbt.tests_advertencia,
                    dbt.tests_fallidos,
                    dbt.modelos_ok,
                    dbt.modelos_error,
                )
                if not dbt.exito:
                    # El watermark NO avanza: el próximo run reprocesa esta misma ventana
                    raise DbtFallido(dbt)

            with Paso("Avanzar watermark"):
                audit.actualizar_watermark(conn_audit, ventana.hasta, run_id)

            audit.finalizar_run(
                conn_audit,
                run_id,
                "exito",
                ventana.desde,
                ventana.hasta,
                tests_ok=dbt.tests_ok + dbt.tests_advertencia,
                tests_fallidos=dbt.tests_fallidos,
            )
            return 0

        except Exception as exc:
            mensaje = audit.sanitizar_error(f"{type(exc).__name__}: {exc}")
            log.error("Pipeline fallido: %s", mensaje)
            resumen = exc.resumen if isinstance(exc, DbtFallido) else None
            audit.finalizar_run(
                conn_audit,
                run_id,
                "fallido",
                ventana.desde if ventana else None,
                ventana.hasta if ventana else None,
                error=mensaje,
                tests_ok=(resumen.tests_ok + resumen.tests_advertencia) if resumen else None,
                tests_fallidos=resumen.tests_fallidos if resumen else None,
            )
            return 1


def _dry_run(cfg, dias_override: int | None) -> int:
    """Calcula la ventana y cuenta filas sin escribir en la base."""
    directorio = cfg.dir_datos / "olist"
    extract_olist.descargar_dataset(directorio)
    datos = extract_olist.leer_dataset(directorio)
    fecha_min, fecha_max = rango_de_datos(datos["orders"])
    with conectar(autocommit=True) as conn:
        watermark = audit.leer_watermark(conn)
    ventana = calcular_ventana(
        watermark, fecha_min, fecha_max, cfg.batch_days, cfg.fecha_carga_inicial, dias_override
    )
    log.info("[dry-run] Watermark: %s | Ventana: %s", watermark, ventana or "sin datos nuevos")
    if ventana:
        for nombre, df in extraer_lote(datos, ventana).items():
            log.info("[dry-run] %-22s %8d filas", nombre, len(df))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Pipeline ETL de ventas retail (Olist)")
    parser.add_argument(
        "--dias", type=int, default=None, help="Días a cargar en este run (ignora BATCH_DAYS)"
    )
    parser.add_argument("--dry-run", action="store_true", help="No escribe en la base de datos")
    args = parser.parse_args()

    configurar_logging()
    inicio = time.perf_counter()
    codigo = ejecutar(args.dias, args.dry_run)
    log.info("Pipeline terminado en %.1f s con código %d", time.perf_counter() - inicio, codigo)
    return codigo


if __name__ == "__main__":
    sys.exit(main())
