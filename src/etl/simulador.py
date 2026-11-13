"""Simulador de llegada de datos.

Olist es histórico (2016-2018) y no cambia. Para simular un negocio vivo, cada
ejecución "recibe" el siguiente bloque de días de pedidos, según la fecha de compra
(`order_purchase_timestamp`), controlado por un watermark en `control.watermark`.

Reglas:
  - Primera ejecución (sin watermark): carga inicial desde la primera fecha del
    dataset hasta FECHA_CARGA_INICIAL.
  - Siguientes: desde (watermark + 1 día) hasta (watermark + BATCH_DAYS días),
    sin pasar de la última fecha del dataset.
  - Si el watermark ya alcanzó la última fecha: no hay datos nuevos (None).

Las tablas hijas (items, pagos, reseñas) llegan junto con sus pedidos; clientes,
productos y vendedores llegan cuando un pedido del lote los referencia.
"""

import logging
from dataclasses import dataclass
from datetime import date, timedelta

import pandas as pd

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Ventana:
    """Rango de fechas de compra (ambos extremos inclusive) que llega en un run."""

    desde: date
    hasta: date
    es_carga_inicial: bool = False

    @property
    def dias(self) -> int:
        return (self.hasta - self.desde).days + 1

    def __str__(self) -> str:
        tipo = "carga inicial" if self.es_carga_inicial else "incremental"
        return f"{self.desde} → {self.hasta} ({self.dias} días, {tipo})"


def calcular_ventana(
    ultima_fecha_cargada: date | None,
    fecha_min_datos: date,
    fecha_max_datos: date,
    batch_days: int,
    fecha_carga_inicial: date,
    dias_override: int | None = None,
) -> Ventana | None:
    """Calcula la ventana de la siguiente ejecución (o None si no hay datos nuevos)."""
    if batch_days < 1 or (dias_override is not None and dias_override < 1):
        raise ValueError("El número de días por lote debe ser >= 1")
    if fecha_min_datos > fecha_max_datos:
        raise ValueError("Rango de datos inválido: fecha mínima posterior a la máxima")

    dias = dias_override or batch_days

    # Primera ejecución: carga inicial
    if ultima_fecha_cargada is None:
        if fecha_carga_inicial >= fecha_min_datos:
            hasta = min(fecha_carga_inicial, fecha_max_datos)
        else:  # fecha inicial configurada antes del dataset: se usa un lote normal
            hasta = min(fecha_min_datos + timedelta(days=dias - 1), fecha_max_datos)
        return Ventana(fecha_min_datos, hasta, es_carga_inicial=True)

    # Ya no quedan datos por "recibir"
    if ultima_fecha_cargada >= fecha_max_datos:
        return None

    desde = max(ultima_fecha_cargada + timedelta(days=1), fecha_min_datos)
    hasta = min(ultima_fecha_cargada + timedelta(days=dias), fecha_max_datos)
    return Ventana(desde, hasta)


def fechas_de_compra(orders: pd.DataFrame) -> pd.Series:
    """Fecha (sin hora) de compra de cada pedido; NaT si el texto no es válido."""
    return pd.to_datetime(
        orders["order_purchase_timestamp"], errors="coerce", format="%Y-%m-%d %H:%M:%S"
    ).dt.date


def rango_de_datos(orders: pd.DataFrame) -> tuple[date, date]:
    """Primera y última fecha de compra presentes en el dataset."""
    fechas = fechas_de_compra(orders).dropna()
    if fechas.empty:
        raise ValueError("El archivo de pedidos no tiene fechas de compra válidas")
    return fechas.min(), fechas.max()


def extraer_lote(datos: dict[str, pd.DataFrame], ventana: Ventana) -> dict[str, pd.DataFrame]:
    """Filtra las tablas de Olist a lo que "llega" en la ventana.

    `datos` debe contener las claves: orders, order_items, order_payments,
    order_reviews, customers, products, sellers, category_translation.
    """
    orders = datos["orders"]
    fechas = fechas_de_compra(orders)
    invalidas = int(fechas.isna().sum())
    if invalidas:
        log.warning("%d pedidos sin fecha de compra válida: no entran en ningún lote", invalidas)

    en_ventana = fechas.notna() & (fechas >= ventana.desde) & (fechas <= ventana.hasta)
    lote_orders = orders[en_ventana]
    ids_pedido = set(lote_orders["order_id"])

    def por_pedido(nombre: str) -> pd.DataFrame:
        df = datos[nombre]
        return df[df["order_id"].isin(ids_pedido)]

    lote_items = por_pedido("order_items")
    customers = datos["customers"]
    products = datos["products"]
    sellers = datos["sellers"]

    return {
        "orders": lote_orders,
        "order_items": lote_items,
        "order_payments": por_pedido("order_payments"),
        "order_reviews": por_pedido("order_reviews"),
        "customers": customers[customers["customer_id"].isin(set(lote_orders["customer_id"]))],
        "products": products[products["product_id"].isin(set(lote_items["product_id"]))],
        "sellers": sellers[sellers["seller_id"].isin(set(lote_items["seller_id"]))],
        # Tabla de referencia pequeña: llega completa en cada run
        "category_translation": datos["category_translation"],
    }
