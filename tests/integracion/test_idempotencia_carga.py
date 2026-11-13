"""Test de integración: la carga a raw es idempotente.

Se ejecuta contra la base real (Neon) en un esquema temporal que se elimina al
final, sin tocar `raw`. Se omite automáticamente si no hay DATABASE_URL (por
ejemplo en el CI de pull requests).
"""

import uuid
from datetime import date

import pandas as pd
import pytest

pytestmark = pytest.mark.integracion

try:
    from etl.config import obtener_database_url

    obtener_database_url()
    HAY_BASE = True
except Exception:
    HAY_BASE = False

DESDE, HASTA = date(2018, 1, 1), date(2018, 1, 7)


@pytest.fixture
def conn_y_esquema():
    if not HAY_BASE:
        pytest.skip("Sin DATABASE_URL: se omite el test de integración")
    from psycopg import sql

    from etl.db import conectar

    esquema = f"test_raw_{uuid.uuid4().hex[:8]}"
    conn = conectar()
    tablas = ["olist_orders", "olist_order_items", "olist_products"]
    conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(esquema)))
    for t in tablas:
        conn.execute(
            sql.SQL("CREATE TABLE {} (LIKE {} INCLUDING ALL)").format(
                sql.Identifier(esquema, t), sql.Identifier("raw", t)
            )
        )
    conn.commit()
    try:
        yield conn, esquema
    finally:
        conn.rollback()
        conn.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(esquema)))
        conn.commit()
        conn.close()


def _lote(estado_o1: str = "delivered") -> dict[str, pd.DataFrame]:
    return {
        "orders": pd.DataFrame(
            {
                "order_id": ["o1", "o2"],
                "customer_id": ["c1", "c2"],
                "order_status": [estado_o1, "shipped"],
                "order_purchase_timestamp": ["2018-01-01 10:00:00", "2018-01-02 11:00:00"],
                "order_approved_at": [None, None],
                "order_delivered_carrier_date": [None, None],
                "order_delivered_customer_date": [None, None],
                "order_estimated_delivery_date": ["2018-01-20 00:00:00", None],
            }
        ),
        "order_items": pd.DataFrame(
            {
                "order_id": ["o1", "o1", "o2"],
                "order_item_id": ["1", "2", "1"],
                "product_id": ["p1", "p2", "p1"],
                "seller_id": ["s1", "s1", "s2"],
                "shipping_limit_date": [None, None, None],
                "price": ["10.50", "20.00", "5.00"],
                "freight_value": ["1.00", "2.00", "0.50"],
            }
        ),
        "products": pd.DataFrame(
            {
                "product_id": ["p1", "p2"],
                "product_category_name": ["beleza_saude", None],
                "product_name_lenght": ["40", None],
                "product_description_lenght": ["200", None],
                "product_photos_qty": ["1", None],
                "product_weight_g": ["500", None],
                "product_length_cm": ["10", None],
                "product_height_cm": ["5", None],
                "product_width_cm": ["8", None],
            }
        ),
    }


def _contar(conn, esquema: str, tabla: str) -> int:
    from psycopg import sql

    return conn.execute(
        sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(esquema, tabla))
    ).fetchone()[0]


def test_cargar_dos_veces_el_mismo_lote_no_duplica(conn_y_esquema):
    from etl.load_raw import cargar_lote_olist

    conn, esquema = conn_y_esquema
    for _ in range(2):
        cargar_lote_olist(conn, _lote(), run_id=None, desde=DESDE, hasta=HASTA, esquema=esquema)
        conn.commit()

    assert _contar(conn, esquema, "olist_orders") == 2
    assert _contar(conn, esquema, "olist_order_items") == 3
    assert _contar(conn, esquema, "olist_products") == 2


def test_recarga_reemplaza_valores_actualizados(conn_y_esquema):
    from psycopg import sql

    from etl.load_raw import cargar_lote_olist

    conn, esquema = conn_y_esquema
    cargar_lote_olist(conn, _lote("shipped"), None, DESDE, HASTA, esquema=esquema)
    cargar_lote_olist(conn, _lote("delivered"), None, DESDE, HASTA, esquema=esquema)
    conn.commit()

    estados = conn.execute(
        sql.SQL("SELECT order_status FROM {} WHERE order_id = 'o1'").format(
            sql.Identifier(esquema, "olist_orders")
        )
    ).fetchall()
    assert estados == [("delivered",)]


def test_error_a_mitad_de_lote_revierte_todo(conn_y_esquema):
    from etl.load_raw import cargar_lote_olist

    conn, esquema = conn_y_esquema
    lote = _lote()
    lote["order_items"]["columna_inexistente"] = "x"  # provoca error en el COPY
    import psycopg

    with pytest.raises(psycopg.errors.UndefinedColumn):
        cargar_lote_olist(conn, lote, None, DESDE, HASTA, esquema=esquema)
    conn.rollback()

    assert _contar(conn, esquema, "olist_orders") == 0  # orders se cargó antes, pero se revirtió
