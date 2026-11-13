"""Carga idempotente a la capa raw.

Estrategia "borrar por clave e insertar" dentro de UNA transacción:
  1. COPY del lote a una tabla temporal (rápido, sin round-trips por fila).
  2. DELETE en la tabla raw de las filas cuyas claves vienen en el lote.
  3. INSERT desde la temporal.

Si el mismo lote se carga dos veces, el paso 2 elimina lo cargado antes y el
resultado es idéntico: no se duplican filas. Si algo falla, la transacción
completa se revierte.
"""

import logging
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

import pandas as pd
import psycopg
from psycopg import sql

from etl.extract_fx import Observacion

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class TablaRaw:
    """Destino raw de una tabla de Olist y su clave para reemplazar filas."""

    nombre: str
    clave: str


# Nombre lógico (extract_olist.ARCHIVOS) -> tabla raw + clave de reemplazo.
# Las tablas hijas se reemplazan por order_id: si un pedido vuelve a llegar,
# llegan de nuevo TODOS sus ítems/pagos/reseñas.
TABLAS_OLIST = {
    "orders": TablaRaw("olist_orders", "order_id"),
    "order_items": TablaRaw("olist_order_items", "order_id"),
    "order_payments": TablaRaw("olist_order_payments", "order_id"),
    "order_reviews": TablaRaw("olist_order_reviews", "order_id"),
    "customers": TablaRaw("olist_customers", "customer_id"),
    "products": TablaRaw("olist_products", "product_id"),
    "sellers": TablaRaw("olist_sellers", "seller_id"),
    "category_translation": TablaRaw("olist_category_translation", "product_category_name"),
}

COLUMNAS_META = ("_run_id", "_ventana_desde", "_ventana_hasta")


def _a_filas(df: pd.DataFrame, meta: tuple) -> Iterable[tuple]:
    """Filas del DataFrame (NaN -> None) con las columnas de metadatos al final."""
    for fila in df.itertuples(index=False, name=None):
        yield tuple(None if pd.isna(v) else v for v in fila) + meta


def cargar_tabla(
    conn: psycopg.Connection,
    tabla: TablaRaw,
    df: pd.DataFrame,
    run_id: int | None,
    desde: date,
    hasta: date,
    esquema: str = "raw",
) -> int:
    """Reemplaza en `esquema.tabla` las filas cuyas claves vienen en `df`.

    Devuelve el número de filas insertadas. No hace commit: el llamador
    controla la transacción para que todo el lote sea atómico.
    """
    if df.empty:
        return 0

    destino = sql.Identifier(esquema, tabla.nombre)
    temporal = sql.Identifier(f"tmp_{tabla.nombre}")
    columnas = list(df.columns) + list(COLUMNAS_META)
    lista_cols = sql.SQL(", ").join(map(sql.Identifier, columnas))
    clave = sql.Identifier(tabla.clave)

    with conn.cursor() as cur:
        cur.execute(
            sql.SQL("CREATE TEMP TABLE {} (LIKE {} INCLUDING DEFAULTS) ON COMMIT DROP").format(
                temporal, destino
            )
        )
        with cur.copy(sql.SQL("COPY {} ({}) FROM STDIN").format(temporal, lista_cols)) as copy:
            for fila in _a_filas(df, (run_id, desde, hasta)):
                copy.write_row(fila)

        cur.execute(
            sql.SQL(
                "DELETE FROM {d} t USING (SELECT DISTINCT {k} FROM {tmp}) l WHERE t.{k} = l.{k}"
            ).format(d=destino, k=clave, tmp=temporal)
        )
        borradas = cur.rowcount
        cur.execute(
            sql.SQL("INSERT INTO {} ({}) SELECT {} FROM {}").format(
                destino, lista_cols, lista_cols, temporal
            )
        )
        insertadas = cur.rowcount
        cur.execute(sql.SQL("DROP TABLE {}").format(temporal))

    log.info(
        "%-32s leídas=%7d  reemplazadas=%7d  insertadas=%7d",
        f"{esquema}.{tabla.nombre}",
        len(df),
        borradas,
        insertadas,
    )
    return insertadas


def cargar_lote_olist(
    conn: psycopg.Connection,
    lote: dict[str, pd.DataFrame],
    run_id: int | None,
    desde: date,
    hasta: date,
    esquema: str = "raw",
) -> dict[str, tuple[int, int]]:
    """Carga todas las tablas del lote. Devuelve {tabla: (leídas, cargadas)}."""
    conteos = {}
    for nombre, df in lote.items():
        tabla = TABLAS_OLIST[nombre]
        cargadas = cargar_tabla(conn, tabla, df, run_id, desde, hasta, esquema)
        conteos[f"{esquema}.{tabla.nombre}"] = (len(df), cargadas)
    return conteos


def cargar_tipo_cambio(
    conn: psycopg.Connection,
    observaciones: list[Observacion],
    run_id: int | None,
    mensual: bool = False,
    esquema: str = "raw",
) -> int:
    """Upsert de observaciones de tipo de cambio (clave: serie + fecha/periodo)."""
    if not observaciones:
        return 0

    if mensual:
        tabla, col_fecha, col_texto = "tipo_cambio_mensual", "periodo", "periodo_original"
    else:
        tabla, col_fecha, col_texto = "tipo_cambio_diario", "fecha", "fecha_original"

    consulta = sql.SQL(
        "INSERT INTO {t} (fuente, serie, {f}, {ft}, valor_original, _run_id) "
        "VALUES (%s, %s, %s, %s, %s, %s) "
        "ON CONFLICT (serie, {f}) DO UPDATE SET "
        "valor_original = EXCLUDED.valor_original, {ft} = EXCLUDED.{ft}, "
        "_run_id = EXCLUDED._run_id, _cargado_en = now()"
    ).format(
        t=sql.Identifier(esquema, tabla),
        f=sql.Identifier(col_fecha),
        ft=sql.Identifier(col_texto),
    )
    with conn.cursor() as cur:
        cur.executemany(
            consulta,
            [
                (o.fuente, o.serie, o.fecha, o.fecha_original, o.valor_original, run_id)
                for o in observaciones
            ],
        )
    log.info("%-32s upsert=%d", f"{esquema}.{tabla}", len(observaciones))
    return len(observaciones)
