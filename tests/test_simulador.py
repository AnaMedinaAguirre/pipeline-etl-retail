"""Tests del simulador de llegada de datos (cálculo de ventanas y filtrado de lotes)."""

from datetime import date

import pandas as pd
import pytest

from etl.simulador import Ventana, calcular_ventana, extraer_lote, rango_de_datos

MIN, MAX = date(2016, 9, 4), date(2018, 10, 17)
INICIAL = date(2017, 12, 31)


# ---------------------------------------------------------------- calcular_ventana
def test_primera_ejecucion_es_carga_inicial_hasta_fecha_configurada():
    v = calcular_ventana(None, MIN, MAX, batch_days=7, fecha_carga_inicial=INICIAL)
    assert v == Ventana(MIN, INICIAL, es_carga_inicial=True)


def test_ejecucion_incremental_carga_batch_days_desde_el_dia_siguiente():
    v = calcular_ventana(INICIAL, MIN, MAX, batch_days=7, fecha_carga_inicial=INICIAL)
    assert v == Ventana(date(2018, 1, 1), date(2018, 1, 7))
    assert v.dias == 7


def test_dias_override_reemplaza_batch_days():
    v = calcular_ventana(INICIAL, MIN, MAX, 7, INICIAL, dias_override=30)
    assert v.hasta == date(2018, 1, 30)


def test_ultima_ventana_se_recorta_a_la_fecha_maxima():
    v = calcular_ventana(date(2018, 10, 15), MIN, MAX, 7, INICIAL)
    assert v == Ventana(date(2018, 10, 16), MAX)


def test_sin_datos_nuevos_devuelve_none():
    assert calcular_ventana(MAX, MIN, MAX, 7, INICIAL) is None
    assert calcular_ventana(date(2019, 1, 1), MIN, MAX, 7, INICIAL) is None


def test_carga_inicial_posterior_al_dataset_se_recorta():
    v = calcular_ventana(None, MIN, MAX, 7, date(2030, 1, 1))
    assert v.hasta == MAX


def test_carga_inicial_anterior_al_dataset_usa_un_lote_normal():
    v = calcular_ventana(None, MIN, MAX, 7, date(2015, 1, 1))
    assert v == Ventana(MIN, date(2016, 9, 10), es_carga_inicial=True)


def test_ventanas_consecutivas_no_se_solapan_ni_dejan_huecos():
    """Encadenar ejecuciones cubre todo el rango exactamente una vez."""
    watermark, dias_cubiertos = None, 0
    while (v := calcular_ventana(watermark, MIN, MAX, 7, INICIAL)) is not None:
        if watermark is not None:
            assert (v.desde - watermark).days == 1
        dias_cubiertos += v.dias
        watermark = v.hasta
    assert watermark == MAX
    assert dias_cubiertos == (MAX - MIN).days + 1


@pytest.mark.parametrize("dias", [0, -3])
def test_dias_invalidos_lanzan_error(dias):
    with pytest.raises(ValueError):
        calcular_ventana(INICIAL, MIN, MAX, dias, INICIAL)


# ---------------------------------------------------------------- extraer_lote
@pytest.fixture
def datos():
    orders = pd.DataFrame(
        {
            "order_id": ["o1", "o2", "o3", "o4"],
            "customer_id": ["c1", "c2", "c3", "c4"],
            "order_purchase_timestamp": [
                "2018-01-01 00:00:00",  # primer instante de la ventana
                "2018-01-07 23:59:59",  # último instante de la ventana
                "2018-01-08 00:00:00",  # fuera (día siguiente)
                "fecha-invalida",  # no entra en ningún lote
            ],
        }
    )
    items = pd.DataFrame(
        {
            "order_id": ["o1", "o1", "o2", "o3"],
            "product_id": ["p1", "p2", "p1", "p9"],
            "seller_id": ["s1", "s1", "s2", "s9"],
        }
    )
    return {
        "orders": orders,
        "order_items": items,
        "order_payments": pd.DataFrame({"order_id": ["o1", "o2", "o2", "o3"]}),
        "order_reviews": pd.DataFrame({"order_id": ["o2", "o3"]}),
        "customers": pd.DataFrame({"customer_id": ["c1", "c2", "c3", "c4"]}),
        "products": pd.DataFrame({"product_id": ["p1", "p2", "p9"]}),
        "sellers": pd.DataFrame({"seller_id": ["s1", "s2", "s9"]}),
        "category_translation": pd.DataFrame({"product_category_name": ["a", "b"]}),
    }


def test_extraer_lote_filtra_por_fecha_de_compra_inclusive(datos):
    lote = extraer_lote(datos, Ventana(date(2018, 1, 1), date(2018, 1, 7)))
    assert set(lote["orders"]["order_id"]) == {"o1", "o2"}


def test_extraer_lote_trae_tablas_hijas_y_entidades_referenciadas(datos):
    lote = extraer_lote(datos, Ventana(date(2018, 1, 1), date(2018, 1, 7)))
    assert len(lote["order_items"]) == 3
    assert len(lote["order_payments"]) == 3
    assert list(lote["order_reviews"]["order_id"]) == ["o2"]
    assert set(lote["customers"]["customer_id"]) == {"c1", "c2"}
    assert set(lote["products"]["product_id"]) == {"p1", "p2"}
    assert set(lote["sellers"]["seller_id"]) == {"s1", "s2"}
    assert len(lote["category_translation"]) == 2  # referencia: llega completa


def test_extraer_lote_vacio_si_no_hay_pedidos_en_la_ventana(datos):
    lote = extraer_lote(datos, Ventana(date(2020, 1, 1), date(2020, 1, 7)))
    assert lote["orders"].empty and lote["order_items"].empty and lote["customers"].empty


def test_rango_de_datos_ignora_fechas_invalidas(datos):
    assert rango_de_datos(datos["orders"]) == (date(2018, 1, 1), date(2018, 1, 8))
